"""
Real (minimal) owner authentication: signup/login/logout backed by Postgres
(Supabase, via db.py), session tokens in an HttpOnly cookie. No third-party
auth dependency -- password hashing uses stdlib hashlib.scrypt (a real, slow,
salted KDF) rather than pulling in bcrypt/passlib, consistent with this
project's zero-new-dependency MVP approach. Shares the same database as
menu_store.py.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

import psycopg

from db import get_connection

SESSION_TTL = timedelta(days=30)

_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32


def _init_auth_tables(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS owners (
            owner_id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_token TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """
    )
    # These two tables hold password hashes and live session tokens --
    # Supabase's separate auto-exposed REST API must never be able to read
    # them. Our app only ever connects here directly as the table-owning
    # role (which bypasses RLS), so this costs us nothing.
    conn.execute("ALTER TABLE owners ENABLE ROW LEVEL SECURITY")
    conn.execute("ALTER TABLE sessions ENABLE ROW LEVEL SECURITY")


@contextmanager
def _connection() -> Iterator[psycopg.Connection]:
    with get_connection() as conn:
        _init_auth_tables(conn)
        yield conn


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN
    )
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN
    )
    return hmac.compare_digest(actual, expected)


def signup(email: str, password: str) -> dict[str, Any]:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("A valid email is required")
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    with _connection() as conn:
        existing = conn.execute("SELECT owner_id FROM owners WHERE email = %s", (email,)).fetchone()
        if existing:
            raise ValueError("An account with this email already exists")
        owner_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO owners (owner_id, email, password_hash, created_at) VALUES (%s, %s, %s, %s)",
            (owner_id, email, _hash_password(password), datetime.now(timezone.utc).isoformat()),
        )
    return {"ownerId": owner_id, "email": email}


def login(email: str, password: str) -> dict[str, Any]:
    email = (email or "").strip().lower()
    with _connection() as conn:
        row = conn.execute(
            "SELECT owner_id, password_hash FROM owners WHERE email = %s", (email,)
        ).fetchone()
    if not row or not _verify_password(password, row[1]):
        raise ValueError("Invalid email or password")
    return {"ownerId": row[0], "email": email}


def create_session(owner_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with _connection() as conn:
        conn.execute(
            "INSERT INTO sessions (session_token, owner_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
            (token, owner_id, now.isoformat(), (now + SESSION_TTL).isoformat()),
        )
    return token


def get_owner_for_session(session_token: str | None) -> dict[str, Any] | None:
    if not session_token:
        return None
    with _connection() as conn:
        row = conn.execute(
            "SELECT s.owner_id, s.expires_at, o.email FROM sessions s "
            "JOIN owners o ON o.owner_id = s.owner_id WHERE s.session_token = %s",
            (session_token,),
        ).fetchone()
        if not row:
            return None
        owner_id, expires_at, email = row
        if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
            conn.execute("DELETE FROM sessions WHERE session_token = %s", (session_token,))
            return None
        return {"ownerId": owner_id, "email": email}


def destroy_session(session_token: str | None) -> None:
    if not session_token:
        return
    with _connection() as conn:
        conn.execute("DELETE FROM sessions WHERE session_token = %s", (session_token,))
