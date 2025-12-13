# src/sitrepc2/lss/persist.py

from __future__ import annotations
import sqlite3
from typing import Optional

from sitrepc2.config.paths import get_lss_db_path
from sitrepc2.lss.ids import make_id


def _conn():
    return sqlite3.connect(get_lss_db_path())


# ---------------------------------------------------------------------
# LOCATION HINTS
# ---------------------------------------------------------------------

def persist_location_hint(
    *,
    location_id: str,
    claim_id: str,
    text: str,
    asserted: bool,
    source: str = "lss",
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO location_hints
            (location_id, claim_id, text, asserted, source, enabled)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (location_id, claim_id, text, asserted, source),
        )


# ---------------------------------------------------------------------
# CONTEXT HINTS
# ---------------------------------------------------------------------

def persist_context_hint(
    *,
    kind: str,
    text: str,
    scope: str,
    source: str = "lss",
    post_id: Optional[str] = None,
    section_id: Optional[str] = None,
    claim_id: Optional[str] = None,
    location_id: Optional[str] = None,
) -> None:
    context_id = make_id(
        "context",
        scope,
        kind,
        text,
        post_id or "",
        section_id or "",
        claim_id or "",
        location_id or "",
    )

    with _conn() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO context_hints
            (context_id, kind, text, scope, source,
             post_id, section_id, claim_id, location_id, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                context_id,
                kind,
                text,
                scope,
                source,
                post_id,
                section_id,
                claim_id,
                location_id,
            ),
        )
