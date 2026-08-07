"""
Real, accumulating "lessons learned" memory.

agentic_memory.py's MEMORY_LIBRARY is a static list of 5 hand-written pattern
cards -- useful as a seed, but it never changes no matter how many
businesses get generated, critiqued, or revised. This module is the actual
write side: it records what critique/simulation/reflection found wrong
during a real generation, and what a real owner explicitly had to ask
"Request a Fix" for, so later businesses with a similar vertical/behavioral
archetype can be warned about it in advance.

Same Postgres (Supabase) database as menu_store.py/submissions_store.py, via
db.py (its own table, learned_memories, in the same shared database rather
than a second SQLite file).
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import psycopg

from db import get_connection

# RetrievedMemory.category is a strict Literal shared with MEMORY_LIBRARY's
# hand-written entries -- map each write source onto the closest existing
# bucket rather than widening that type for a new set of values.
_SOURCE_TO_CATEGORY = {
    "critique": "behavioral_pattern",
    "simulation": "workflow_pattern",
    "reflection": "behavioral_pattern",
    "revision_request": "behavioral_pattern",
}


def _init_db(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS learned_memories (
            id TEXT PRIMARY KEY,
            business_id TEXT DEFAULT '',
            vertical TEXT DEFAULT '',
            subtype TEXT DEFAULT '',
            risk_level TEXT DEFAULT 'standard',
            primary_workflow TEXT DEFAULT '',
            behavioral_archetypes TEXT DEFAULT '[]',
            evidence_tags TEXT DEFAULT '[]',
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            recommended_action TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_learned_memories_vertical ON learned_memories(vertical)"
    )


@contextmanager
def _connection() -> Iterator[psycopg.Connection]:
    with get_connection() as conn:
        _init_db(conn)
        yield conn


def record_memory(
    *,
    business_id: str = "",
    vertical: str = "",
    subtype: str = "",
    risk_level: str = "standard",
    primary_workflow: str = "",
    behavioral_archetypes: list[str] | None = None,
    evidence_tags: list[str] | None = None,
    source: str,
    title: str,
    summary: str,
    recommended_action: str = "",
) -> bool:
    """Insert one lesson. Skips (returns False) if a lesson with the exact
    same summary already exists anywhere -- the same critique/simulation
    finding otherwise gets re-inserted every time a business is
    regenerated, quickly drowning out real signal with duplicates."""
    summary = summary.strip()
    if not summary:
        return False
    with _connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM learned_memories WHERE summary = %s LIMIT 1",
            (summary,),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """
            INSERT INTO learned_memories
            (id, business_id, vertical, subtype, risk_level, primary_workflow,
             behavioral_archetypes, evidence_tags, source, title, summary,
             recommended_action, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                business_id,
                vertical,
                subtype,
                risk_level,
                primary_workflow,
                json.dumps(behavioral_archetypes or []),
                json.dumps(evidence_tags or []),
                source,
                title,
                summary,
                recommended_action,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return True


def list_all_memories() -> list[dict[str, Any]]:
    """Every learned memory, already shaped like a MEMORY_LIBRARY entry
    (same key names/set-valued tag fields) so agentic_memory.py's existing
    score_memory_item() can score it with zero changes."""
    with _connection() as conn:
        rows = conn.execute(
            "SELECT vertical, subtype, risk_level, primary_workflow, "
            "behavioral_archetypes, evidence_tags, source, title, summary, "
            "recommended_action FROM learned_memories "
            "ORDER BY created_at DESC LIMIT 200"
        ).fetchall()

    memories: list[dict[str, Any]] = []
    for row in rows:
        (
            vertical, subtype, risk_level, primary_workflow,
            archetypes_json, evidence_json, source, title, summary,
            recommended_action,
        ) = row
        try:
            archetypes = json.loads(archetypes_json)
        except json.JSONDecodeError:
            archetypes = []
        try:
            evidence_tags = json.loads(evidence_json)
        except json.JSONDecodeError:
            evidence_tags = []
        memories.append({
            "memory_id": f"learned:{source}:{uuid.uuid5(uuid.NAMESPACE_URL, title + summary)}",
            "category": _SOURCE_TO_CATEGORY.get(source, "behavioral_pattern"),
            "verticals": {vertical} if vertical else set(),
            "workflows": {primary_workflow} if primary_workflow else set(),
            "behavioral_tags": set(archetypes),
            "evidence_tags": set(evidence_tags),
            "risk_levels": {risk_level} if risk_level else set(),
            "title": title,
            "summary": summary,
            "applicability": f"Learned from a real {source.replace('_', ' ')} on a similar business.",
            "recommended_actions": [recommended_action] if recommended_action else [],
            "anti_patterns": [],
        })
    return memories
