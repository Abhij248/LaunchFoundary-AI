"""
Real (if minimal) persistence for this app: business records (with their
public slug + latest generated preview) and owner-editable menu/catalog
items, both keyed by business_id.

Backed by Postgres (Supabase) via db.py, shared with every other store
module -- moved off local SQLite so data survives redeployment. No per-item
CRUD on menu items (whole-list replace only), no migrations framework.
"""

from __future__ import annotations

import json
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg

from db import get_connection


def _init_db(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_items (
            id TEXT NOT NULL,
            business_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT DEFAULT '',
            description TEXT DEFAULT '',
            price_label TEXT DEFAULT '',
            price_sort_value REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            PRIMARY KEY (business_id, id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_menu_items_business ON menu_items(business_id)"
    )
    conn.execute("ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS image_url TEXT DEFAULT ''")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS business_meta (
            business_id TEXT PRIMARY KEY,
            seeded_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS businesses (
            business_id TEXT PRIMARY KEY,
            owner_id TEXT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            html_preview TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS build_spec_json TEXT DEFAULT ''")
    # The LLM-generated owner dashboard (separate artifact from the
    # customer-facing html_preview) -- empty until generate_code()
    # produces one; the frontend falls back to the hand-coded generic
    # panel when this is empty, never shows a blank page.
    conn.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS admin_html_preview TEXT DEFAULT ''")


@contextmanager
def _connection() -> Iterator[psycopg.Connection]:
    with get_connection() as conn:
        _init_db(conn)
        yield conn


def _row_to_item(row: tuple) -> dict[str, Any]:
    (item_id, _business_id, name, category, description, price_label, price_sort_value, _sort_order, image_url) = row
    return {
        "id": item_id,
        "name": name,
        "category": category,
        "description": description,
        "priceLabel": price_label,
        "priceSortValue": price_sort_value,
        "imageUrl": image_url or "",
    }


def _item_to_row(business_id: str, item: dict[str, Any], sort_order: int) -> tuple:
    return (
        str(item.get("id") or uuid.uuid4()),
        business_id,
        str(item.get("name", "")),
        str(item.get("category", "")),
        str(item.get("description", "")),
        str(item.get("priceLabel", "")),
        float(item.get("priceSortValue") or 0),
        sort_order,
        str(item.get("imageUrl", "")),
    )


def seed_if_new(business_id: str, items: list[dict[str, Any]]) -> bool:
    """Insert items only the first time a business is ever seen.

    Uses a dedicated business_meta guard row rather than a row-count check,
    since the owner deleting every item via the CMS (leaving 0 rows) must
    not look like "never seeded" and trigger a resurrecting reseed.
    """
    if not business_id:
        return False
    with _connection() as conn:
        already_seeded = conn.execute(
            "SELECT 1 FROM business_meta WHERE business_id = %s", (business_id,)
        ).fetchone()
        if already_seeded:
            return False
        conn.execute(
            "INSERT INTO business_meta (business_id, seeded_at) VALUES (%s, %s)",
            (business_id, datetime.now(timezone.utc).isoformat()),
        )
        rows = [
            _item_to_row(business_id, item, index)
            for index, item in enumerate(items or [])
        ]
        if rows:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO menu_items "
                    "(id, business_id, name, category, description, price_label, price_sort_value, sort_order, image_url) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    rows,
                )
        return True


def list_items(business_id: str) -> list[dict[str, Any]]:
    if not business_id:
        return []
    with _connection() as conn:
        rows = conn.execute(
            "SELECT id, business_id, name, category, description, price_label, price_sort_value, sort_order, image_url "
            "FROM menu_items WHERE business_id = %s ORDER BY sort_order ASC",
            (business_id,),
        ).fetchall()
        return [_row_to_item(row) for row in rows]


def replace_items(business_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not business_id:
        return []
    with _connection() as conn:
        conn.execute("DELETE FROM menu_items WHERE business_id = %s", (business_id,))
        rows = [
            _item_to_row(business_id, item, index)
            for index, item in enumerate(items or [])
        ]
        if rows:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO menu_items "
                    "(id, business_id, name, category, description, price_label, price_sort_value, sort_order, image_url) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    rows,
                )
        # Ensure a business_meta row exists so this business is never
        # re-seeded from stale generation-time data after an owner edit.
        conn.execute(
            "INSERT INTO business_meta (business_id, seeded_at) VALUES (%s, %s) "
            "ON CONFLICT (business_id) DO NOTHING",
            (business_id, datetime.now(timezone.utc).isoformat()),
        )
    return list_items(business_id)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return slug or "business"


def _unique_slug(conn: psycopg.Connection, name: str, business_id: str) -> str:
    base = _slugify(name)
    candidate = base
    suffix = 2
    while True:
        row = conn.execute(
            "SELECT business_id FROM businesses WHERE slug = %s", (candidate,)
        ).fetchone()
        if row is None or row[0] == business_id:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


_BUSINESS_COLUMNS = "business_id, owner_id, name, slug, html_preview, created_at, updated_at, admin_html_preview"


def _row_to_business(row: tuple) -> dict[str, Any]:
    (business_id, owner_id, name, slug, html_preview, created_at, updated_at, admin_html_preview) = row
    return {
        "businessId": business_id,
        "ownerId": owner_id,
        "name": name,
        "slug": slug,
        "htmlPreview": html_preview,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "adminHtmlPreview": admin_html_preview or "",
    }


def ensure_business(business_id: str, name: str, owner_id: str | None = None) -> dict[str, Any] | None:
    """Create the business record on first generation; a later regeneration
    just returns the existing row (name/slug are stable once assigned, since
    the slug becomes this business's public URL).

    owner_id is a first-claim: a business created while logged out (owner_id
    NULL) gets linked the first time it's regenerated while logged in, but an
    already-owned business never gets silently reassigned to someone else.
    """
    if not business_id:
        return None
    with _connection() as conn:
        existing = conn.execute(
            f"SELECT {_BUSINESS_COLUMNS} FROM businesses WHERE business_id = %s",
            (business_id,),
        ).fetchone()
        if existing:
            row = _row_to_business(existing)
            if owner_id and not row["ownerId"]:
                conn.execute(
                    "UPDATE businesses SET owner_id = %s WHERE business_id = %s",
                    (owner_id, business_id),
                )
                row["ownerId"] = owner_id
            return row
        now = datetime.now(timezone.utc).isoformat()
        slug = _unique_slug(conn, name or "business", business_id)
        conn.execute(
            "INSERT INTO businesses (business_id, owner_id, name, slug, html_preview, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, '', %s, %s)",
            (business_id, owner_id, name or "Business", slug, now, now),
        )
        row = conn.execute(
            f"SELECT {_BUSINESS_COLUMNS} FROM businesses WHERE business_id = %s",
            (business_id,),
        ).fetchone()
        return _row_to_business(row)


def list_businesses_for_owner(owner_id: str) -> list[dict[str, Any]]:
    if not owner_id:
        return []
    with _connection() as conn:
        rows = conn.execute(
            f"SELECT {_BUSINESS_COLUMNS} FROM businesses WHERE owner_id = %s ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
        return [_row_to_business(row) for row in rows]


def delete_business(business_id: str, owner_id: str) -> bool:
    """Permanently deletes a business and everything scoped to it (menu
    items, seed marker). Requires owner_id to match the business's actual
    owner -- an unowned business (owner_id NULL) can't be deleted this way,
    and neither can someone else's. Returns False if nothing was deleted."""
    if not business_id or not owner_id:
        return False
    with _connection() as conn:
        row = conn.execute(
            "SELECT owner_id FROM businesses WHERE business_id = %s",
            (business_id,),
        ).fetchone()
        if not row or row[0] != owner_id:
            return False
        conn.execute("DELETE FROM businesses WHERE business_id = %s", (business_id,))
        conn.execute("DELETE FROM menu_items WHERE business_id = %s", (business_id,))
        conn.execute("DELETE FROM business_meta WHERE business_id = %s", (business_id,))
        return True


def update_business_preview(business_id: str, html_preview: str) -> None:
    if not business_id:
        return
    with _connection() as conn:
        conn.execute(
            "UPDATE businesses SET html_preview = %s, updated_at = %s WHERE business_id = %s",
            (html_preview, datetime.now(timezone.utc).isoformat(), business_id),
        )


def update_business_admin_preview(business_id: str, admin_html_preview: str) -> None:
    """Separate from update_business_preview: the generated owner dashboard
    is its own artifact for its own audience, not part of the customer page."""
    if not business_id:
        return
    with _connection() as conn:
        conn.execute(
            "UPDATE businesses SET admin_html_preview = %s WHERE business_id = %s",
            (admin_html_preview, business_id),
        )


def get_business_by_slug(slug: str) -> dict[str, Any] | None:
    with _connection() as conn:
        row = conn.execute(
            f"SELECT {_BUSINESS_COLUMNS} FROM businesses WHERE slug = %s",
            (slug,),
        ).fetchone()
        return _row_to_business(row) if row else None


def get_business(business_id: str) -> dict[str, Any] | None:
    if not business_id:
        return None
    with _connection() as conn:
        row = conn.execute(
            f"SELECT {_BUSINESS_COLUMNS} FROM businesses WHERE business_id = %s",
            (business_id,),
        ).fetchone()
        return _row_to_business(row) if row else None


def update_business_build_spec(business_id: str, build_spec: dict[str, Any]) -> None:
    """Stores the exact build_spec used for the most recent generation, so a
    later revision request has real business context to work from instead of
    just the raw HTML."""
    if not business_id:
        return
    with _connection() as conn:
        conn.execute(
            "UPDATE businesses SET build_spec_json = %s WHERE business_id = %s",
            (json.dumps(build_spec), business_id),
        )


def get_business_build_context(business_id: str) -> dict[str, Any] | None:
    """Everything a revision call needs: the business's name/slug, its
    current live HTML, and the build_spec that produced it."""
    if not business_id:
        return None
    with _connection() as conn:
        row = conn.execute(
            "SELECT name, slug, html_preview, build_spec_json FROM businesses WHERE business_id = %s",
            (business_id,),
        ).fetchone()
    if not row:
        return None
    name, slug, html_preview, build_spec_json = row
    try:
        build_spec = json.loads(build_spec_json) if build_spec_json else None
    except json.JSONDecodeError:
        build_spec = None
    return {"name": name, "slug": slug, "htmlPreview": html_preview, "buildSpec": build_spec}
