# src/sitrepc2/review/write.py

from __future__ import annotations
from datetime import datetime
import sqlite3
import uuid

from sitrepc2.config.paths import get_lss_db_path


def _conn():
    return sqlite3.connect(get_lss_db_path())


def write_review_state(
    *,
    entity_type: str,
    entity_id: str,
    stage: str,
    enabled: bool,
    reviewer: str | None = None,
):
    with _conn() as con:
        con.execute(
            """
            INSERT OR REPLACE INTO review_state
            (entity_type, entity_id, stage, enabled, reviewer, reviewed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_id,
                stage,
                1 if enabled else 0,
                reviewer,
                datetime.utcnow().isoformat(),
            ),
        )


def add_review_note(
    *,
    entity_type: str,
    entity_id: str,
    stage: str,
    note: str,
    author: str | None = None,
):
    with _conn() as con:
        con.execute(
            """
            INSERT INTO review_notes
            (note_id, entity_type, entity_id, stage, author, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                entity_type,
                entity_id,
                stage,
                author,
                note,
                datetime.utcnow().isoformat(),
            ),
        )
