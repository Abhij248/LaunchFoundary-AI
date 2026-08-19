"""
Real persistence for customer submissions (orders/reservations/leads),
scoped to business_id. Same Postgres (Supabase) database as menu_store.py/
auth_store.py, via db.py.

Replaces the old postMessage-into-browser-memory approach: that only ever
worked while a business owner happened to have the builder tool's iframe
open in the same tab, and lost everything on refresh. A real customer
visiting a business's standalone /site/{slug} page has no such parent to
message at all, so persisting server-side is the only way submissions
survive there.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg

from db import get_connection

VALID_TYPES = {"order", "reservation", "lead"}
VALID_STATUSES = {"new", "in_progress", "completed", "cancelled"}
DEFAULT_STATUS = "new"


def _init_db(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            type TEXT NOT NULL,
            customer TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            contact TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_submissions_business ON submissions(business_id)"
    )
    conn.execute(f"ALTER TABLE submissions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT '{DEFAULT_STATUS}'")
    # Distinguishes real customer submissions from ones created by the
    # Tier 2 QA smoke-test agent completing a real checkout while testing --
    # those get cleaned up right after, but tagging them immediately on
    # creation means a stray one survives visibly (not silently masquerading
    # as a real order) if cleanup itself fails.
    conn.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'customer'")
    # Real customer names/phone numbers/emails -- Supabase's separate
    # auto-exposed REST API must never be able to read them. Our app only
    # ever connects here directly as the table-owning role (bypasses RLS).
    conn.execute("ALTER TABLE submissions ENABLE ROW LEVEL SECURITY")


@contextmanager
def _connection() -> Iterator[psycopg.Connection]:
    with get_connection() as conn:
        _init_db(conn)
        yield conn


def _row_to_submission(row: tuple) -> dict[str, Any]:
    (sub_id, business_id, type_, customer, summary, contact, created_at, status, source) = row
    return {
        "id": sub_id,
        "businessId": business_id,
        "type": type_,
        "customer": customer,
        "summary": summary,
        "contact": contact,
        "createdAt": created_at,
        "status": status or DEFAULT_STATUS,
        "source": source or "customer",
    }


def create_submission(
    business_id: str, type_: str, customer: str = "", summary: str = "", contact: str = ""
) -> dict[str, Any] | None:
    if not business_id or type_ not in VALID_TYPES:
        return None
    sub_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        conn.execute(
            "INSERT INTO submissions (id, business_id, type, customer, summary, contact, created_at, status, source) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'customer')",
            (sub_id, business_id, type_, customer or "", summary or "", contact or "", now, DEFAULT_STATUS),
        )
    return {
        "id": sub_id, "businessId": business_id, "type": type_,
        "customer": customer or "", "summary": summary or "", "contact": contact or "", "createdAt": now,
        "status": DEFAULT_STATUS, "source": "customer",
    }


def list_submissions(business_id: str) -> list[dict[str, Any]]:
    if not business_id:
        return []
    with _connection() as conn:
        rows = conn.execute(
            "SELECT id, business_id, type, customer, summary, contact, created_at, status, source "
            "FROM submissions WHERE business_id = %s ORDER BY created_at DESC",
            (business_id,),
        ).fetchall()
        return [_row_to_submission(row) for row in rows]


def delete_submissions_for_business(business_id: str) -> None:
    if not business_id:
        return
    with _connection() as conn:
        conn.execute("DELETE FROM submissions WHERE business_id = %s", (business_id,))


def mark_submission_source(submission_id: str, source: str) -> None:
    """Tags a submission's origin right after creation is observed -- used by
    the Tier 2 QA smoke-test harness so a stray test submission is at least
    visually identifiable in the admin dashboard if the subsequent cleanup
    delete fails, instead of silently masquerading as a real customer order."""
    if not submission_id:
        return
    with _connection() as conn:
        conn.execute(
            "UPDATE submissions SET source = %s WHERE id = %s",
            (source, submission_id),
        )


def delete_submission(submission_id: str) -> bool:
    """Removes exactly one submission (the QA smoke-test cleanup path) --
    unlike delete_submissions_for_business, which would also wipe real
    customer history for that business."""
    if not submission_id:
        return False
    with _connection() as conn:
        cur = conn.execute(
            "DELETE FROM submissions WHERE id = %s",
            (submission_id,),
        )
        return cur.rowcount > 0


def update_submission_status(business_id: str, submission_id: str, status: str) -> dict[str, Any] | None:
    """Owner-driven order/booking/lead workflow -- the one thing the admin
    dashboard was missing entirely: a way to act on a submission after it
    arrives, not just look at it."""
    if not business_id or status not in VALID_STATUSES:
        return None
    with _connection() as conn:
        cur = conn.execute(
            "UPDATE submissions SET status = %s WHERE id = %s AND business_id = %s",
            (status, submission_id, business_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT id, business_id, type, customer, summary, contact, created_at, status, source "
            "FROM submissions WHERE id = %s",
            (submission_id,),
        ).fetchone()
    return _row_to_submission(row) if row else None
