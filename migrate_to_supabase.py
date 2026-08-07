"""
One-off script: copies every row out of the old local SQLite files
(~/.launchfoundry/menu_items.db and ~/.launchfoundry/learned_memory.db)
into the new Supabase Postgres database, now that every store module talks
to Postgres exclusively (see db.py). Safe to re-run -- every insert uses
ON CONFLICT DO NOTHING, so already-migrated rows are silently skipped.

Usage:
    DATABASE_URL="postgresql://...supabase connection string..." python migrate_to_supabase.py

Run this once, after creating the Supabase project and before pointing the
running app at it for real.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def _load_local_env() -> None:
    """Same minimal .env parser amd_inference_server.py uses -- duplicated
    here rather than imported, so this standalone script doesn't have to
    pull in the whole app (langgraph, the agentic pipeline, etc.) just to
    read DATABASE_URL."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()

from db import get_connection
import menu_store
import auth_store
import submissions_store
import custom_entities_store
import learned_memory_store

MENU_DB = Path.home() / ".launchfoundry" / "menu_items.db"
MEMORY_DB = Path.home() / ".launchfoundry" / "learned_memory.db"

# (source sqlite file, table name, column list in insert order)
TABLES = [
    (MENU_DB, "businesses", [
        "business_id", "owner_id", "name", "slug", "html_preview",
        "created_at", "updated_at", "build_spec_json", "admin_html_preview",
    ]),
    (MENU_DB, "menu_items", [
        "id", "business_id", "name", "category", "description",
        "price_label", "price_sort_value", "sort_order", "image_url",
    ]),
    (MENU_DB, "business_meta", ["business_id", "seeded_at"]),
    (MENU_DB, "owners", ["owner_id", "email", "password_hash", "created_at"]),
    (MENU_DB, "sessions", ["session_token", "owner_id", "created_at", "expires_at"]),
    (MENU_DB, "submissions", [
        "id", "business_id", "type", "customer", "summary", "contact",
        "created_at", "status", "source",
    ]),
    (MENU_DB, "custom_entities", [
        "id", "business_id", "entity_type", "data_json", "created_at", "updated_at",
    ]),
    (MENU_DB, "resource_claims", [
        "business_id", "entity_type", "entity_id", "resource_key", "claimed_at",
    ]),
    (MEMORY_DB, "learned_memories", [
        "id", "business_id", "vertical", "subtype", "risk_level", "primary_workflow",
        "behavioral_archetypes", "evidence_tags", "source", "title", "summary",
        "recommended_action", "created_at",
    ]),
]


def _read_sqlite_rows(sqlite_path: Path, table: str, columns: list[str]) -> list[tuple]:
    if not sqlite_path.exists():
        print(f"  (skip {table}: {sqlite_path} not found)")
        return []
    conn = sqlite3.connect(sqlite_path)
    try:
        col_list = ", ".join(columns)
        return conn.execute(f"SELECT {col_list} FROM {table}").fetchall()
    except sqlite3.OperationalError as exc:
        print(f"  (skip {table}: {exc})")
        return []
    finally:
        conn.close()


def main() -> None:
    with get_connection() as conn:
        # Ensure every table exists in Postgres before copying into it.
        menu_store._init_db(conn)
        auth_store._init_auth_tables(conn)
        submissions_store._init_db(conn)
        custom_entities_store._init_db(conn)
        learned_memory_store._init_db(conn)

        total = 0
        for sqlite_path, table, columns in TABLES:
            rows = _read_sqlite_rows(sqlite_path, table, columns)
            if not rows:
                print(f"  {table}: 0 rows")
                continue
            placeholders = ", ".join(["%s"] * len(columns))
            col_list = ", ".join(columns)
            with conn.cursor() as cur:
                cur.executemany(
                    f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
                    f"ON CONFLICT DO NOTHING",
                    rows,
                )
            print(f"  {table}: {len(rows)} rows migrated")
            total += len(rows)

    print(f"\nDone. {total} rows copied into Supabase.")


if __name__ == "__main__":
    main()
