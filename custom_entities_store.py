"""
Generic, schemaless per-business data store -- the actual fix for
businesses whose real backend need doesn't fit the fixed items/submissions
schema (e.g. a theatre's showtimes with per-seat availability).

This deliberately does NOT do dynamic SQL schema generation. The model
decides the *shape* of its data (as a JSON blob) via real tool-calling
during generation (see code_generator.py's _provision_custom_backend);
entity_type is just a label it picks (e.g. "showtime"), and data_json holds
whatever fields it chose. resource_claims provides the one thing that
actually needed to be a real, atomic backend primitive: "don't let two
people grab the same limited slot" -- the PRIMARY KEY constraint below is
what prevents two customers from claiming the same seat, not an
application-level check-then-write (which would have the exact race
condition this whole thing exists to avoid).

Same Postgres (Supabase) database as menu_store.py/submissions_store.py, via
db.py.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg

from db import get_connection

# Basic abuse/growth guard -- generous for real use, just stops a runaway
# tool-calling loop or a malicious client from writing unbounded rows.
MAX_ENTITIES_PER_TYPE = 500


def _init_db(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_entities (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            data_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_custom_entities_lookup ON custom_entities(business_id, entity_type)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS resource_claims (
            business_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            resource_key TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            PRIMARY KEY (business_id, entity_type, entity_id, resource_key)
        )
        """
    )


@contextmanager
def _connection() -> Iterator[psycopg.Connection]:
    with get_connection() as conn:
        _init_db(conn)
        yield conn


def create_entity(business_id: str, entity_type: str, data: dict[str, Any]) -> dict[str, Any] | None:
    if not business_id or not entity_type:
        return None
    entity_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM custom_entities WHERE business_id = %s AND entity_type = %s",
            (business_id, entity_type),
        ).fetchone()[0]
        if count >= MAX_ENTITIES_PER_TYPE:
            return None
        conn.execute(
            "INSERT INTO custom_entities (id, business_id, entity_type, data_json, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (entity_id, business_id, entity_type, json.dumps(data), now, now),
        )
    return {"id": entity_id, "entityType": entity_type, "data": data, "createdAt": now, "updatedAt": now}


def list_entities(business_id: str, entity_type: str) -> list[dict[str, Any]]:
    if not business_id or not entity_type:
        return []
    with _connection() as conn:
        rows = conn.execute(
            "SELECT id, data_json, created_at, updated_at FROM custom_entities "
            "WHERE business_id = %s AND entity_type = %s ORDER BY created_at ASC",
            (business_id, entity_type),
        ).fetchall()
    results: list[dict[str, Any]] = []
    for entity_id, data_json, created_at, updated_at in rows:
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError:
            data = {}
        results.append({
            "id": entity_id, "entityType": entity_type, "data": data,
            "createdAt": created_at, "updatedAt": updated_at,
        })
    return results


def update_entity(business_id: str, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    if not business_id or not entity_id:
        return None
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        cur = conn.execute(
            "UPDATE custom_entities SET data_json = %s, updated_at = %s WHERE id = %s AND business_id = %s",
            (json.dumps(data), now, entity_id, business_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT entity_type, data_json, created_at, updated_at FROM custom_entities WHERE id = %s",
            (entity_id,),
        ).fetchone()
    if not row:
        return None
    entity_type, data_json, created_at, updated_at = row
    return {
        "id": entity_id, "entityType": entity_type, "data": json.loads(data_json),
        "createdAt": created_at, "updatedAt": updated_at,
    }


def claim_resource(business_id: str, entity_type: str, entity_id: str, resource_key: str) -> bool:
    """Atomically claims one resource_key (e.g. one specific seat) within
    one entity (e.g. one showtime). Returns False if it was already
    claimed -- the PRIMARY KEY constraint is what makes this safe under
    concurrent requests, not an application-level check-then-write."""
    if not (business_id and entity_type and entity_id and resource_key):
        return False
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        try:
            conn.execute(
                "INSERT INTO resource_claims (business_id, entity_type, entity_id, resource_key, claimed_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (business_id, entity_type, entity_id, resource_key, now),
            )
        except psycopg.errors.UniqueViolation:
            # Postgres poisons the rest of the transaction after any error
            # until a rollback happens -- unlike sqlite3, where catching
            # IntegrityError left the connection immediately usable again.
            conn.rollback()
            return False
    return True


def release_claim(business_id: str, entity_type: str, entity_id: str, resource_key: str) -> bool:
    """Undoes one claim -- used by the Tier 2 QA smoke-test harness to release
    a real seat/slot it claimed while test-driving a checkout flow, so testing
    never permanently costs a real customer a resource."""
    if not (business_id and entity_type and entity_id and resource_key):
        return False
    with _connection() as conn:
        cur = conn.execute(
            "DELETE FROM resource_claims WHERE business_id = %s AND entity_type = %s "
            "AND entity_id = %s AND resource_key = %s",
            (business_id, entity_type, entity_id, resource_key),
        )
        return cur.rowcount > 0


def list_claims(business_id: str, entity_type: str, entity_id: str) -> list[str]:
    if not (business_id and entity_type and entity_id):
        return []
    with _connection() as conn:
        rows = conn.execute(
            "SELECT resource_key FROM resource_claims WHERE business_id = %s AND entity_type = %s AND entity_id = %s",
            (business_id, entity_type, entity_id),
        ).fetchall()
    return [row[0] for row in rows]


def delete_entities_for_business(business_id: str) -> None:
    if not business_id:
        return
    with _connection() as conn:
        conn.execute("DELETE FROM custom_entities WHERE business_id = %s", (business_id,))
        conn.execute("DELETE FROM resource_claims WHERE business_id = %s", (business_id,))
