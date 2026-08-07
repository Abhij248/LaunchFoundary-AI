"""
Shared Postgres (Supabase) connection provider for every store module in
this app (menu_store, auth_store, submissions_store, custom_entities_store,
learned_memory_store) -- replaces the old per-file sqlite3.connect(DB_PATH)
pattern now that persistence needs to survive redeployment.

Connects via DATABASE_URL (the connection string Supabase gives you under
Project Settings > Database > Connection string). If you end up hosting the
backend somewhere serverless (e.g. Vercel functions), use Supabase's pooled
connection string (port 6543, "Transaction" mode) instead of the direct one
(port 5432) -- serverless invocations open many short-lived connections and
can exhaust Postgres's connection limit against the direct connection.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set -- this app requires a Postgres connection "
            "string (from Supabase: Project Settings > Database > Connection "
            "string) in the environment or .env file."
        )
    return url


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(_database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
