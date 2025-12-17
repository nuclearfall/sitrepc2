# src/sitrepc2/lss/persist.py

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from sitrepc2.config.paths import get_records_db_path

UTC = timezone.utc


# ---------------------------------------------------------------------
# DB connection helpers
# ---------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    """
    Open a connection to the authoritative records database.

    Foreign key enforcement is enabled explicitly, as SQLite
    does NOT enable it by default.
    """
    con = sqlite3.connect(get_records_db_path())
    con.execute("PRAGMA foreign_keys = ON;")
    return con



def _utc_now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------
# LSS RUNS
# ---------------------------------------------------------------------

def create_lss_run(
    *,
    ingest_post_id: int,
    engine: str,
    engine_version: Optional[str] = None,
    model: Optional[str] = None,
) -> int:
    """
    Create a new LSS run for a single ingest post.
    Returns the lss_runs.id primary key.
    """
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO lss_runs
                (ingest_post_id, started_at, engine, engine_version, model)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                ingest_post_id,
                _utc_now_iso(),
                engine,
                engine_version,
                model,
            ),
        )
        return int(cur.lastrowid)


def complete_lss_run(lss_run_id: int) -> None:
    """Mark an LSS run as completed."""
    with _conn() as con:
        con.execute(
            """
            UPDATE lss_runs
            SET completed_at = ?
            WHERE id = ?
            """,
            (_utc_now_iso(), lss_run_id),
        )


# ---------------------------------------------------------------------
# SECTIONS
# ---------------------------------------------------------------------

def persist_section(
    *,
    lss_run_id: int,
    ingest_post_id: int,
    text: str,
    ordinal: int,
    start_token: Optional[int] = None,
    end_token: Optional[int] = None,
) -> int:
    """
    Persist a detected section and return its database ID.
    """
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO lss_sections
                (lss_run_id, ingest_post_id, text,
                 start_token, end_token, ordinal)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                lss_run_id,
                ingest_post_id,
                text,
                start_token,
                end_token,
                ordinal,
            ),
        )
        return int(cur.lastrowid)


# ---------------------------------------------------------------------
# EVENTS
# ---------------------------------------------------------------------

def persist_event(
    *,
    lss_run_id: int,
    ingest_post_id: int,
    event_uid: str,
    label: str,
    search_phrase: str,
    text: str,
    start_token: int,
    end_token: int,
    ordinal: int,
    similarity: Optional[float],
    negated: bool,
    uncertain: bool,
    involves_coreference: bool,
    section_id: Optional[int] = None,
) -> int:
    """
    Persist a single LSS-extracted event and return its database ID.
    """
    with _conn() as con:
        cur = con.execute(
            """
            INSERT INTO lss_events
                (lss_run_id, ingest_post_id, section_id,
                 event_uid, label, search_phrase,
                 text, start_token, end_token,
                 similarity, negated, uncertain,
                 involves_coreference, ordinal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lss_run_id,
                ingest_post_id,
                section_id,
                event_uid,
                label,
                search_phrase,
                text,
                start_token,
                end_token,
                similarity,
                int(negated),
                int(uncertain),
                int(involves_coreference),
                ordinal,
            ),
        )
        return int(cur.lastrowid)


# ---------------------------------------------------------------------
# ROLE CANDIDATES
# ---------------------------------------------------------------------

def persist_role_candidate(
    *,
    lss_event_id: int,
    role_kind: str,
    document_word: str,
    document_phrase: Optional[str],
    start_token: int,
    end_token: int,
    match_type: Optional[str],
    negated: bool,
    uncertain: bool,
    involves_coreference: bool,
    similarity: Optional[float],
    explanation: Optional[str],
) -> None:
    """
    Persist a single role candidate derived from a Holmes WordMatch.
    """
    with _conn() as con:
        con.execute(
            """
            INSERT INTO lss_role_candidates
                (lss_event_id, role_kind,
                 document_word, document_phrase,
                 start_token, end_token,
                 match_type, negated, uncertain,
                 involves_coreference, similarity,
                 explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lss_event_id,
                role_kind,
                document_word,
                document_phrase,
                start_token,
                end_token,
                match_type,
                int(negated),
                int(uncertain),
                int(involves_coreference),
                similarity,
                explanation,
            ),
        )


# ---------------------------------------------------------------------
# CONTEXT SPANS
# ---------------------------------------------------------------------

def persist_context_span(
    *,
    lss_run_id: int,
    ingest_post_id: int,
    ctx_kind: str,
    text: str,
    start_token: Optional[int] = None,
    end_token: Optional[int] = None,
) -> None:
    """
    Persist a contextual span detected by LSS.
    Contexts are not yet bound to events or locations.
    """
    with _conn() as con:
        con.execute(
            """
            INSERT INTO lss_context_spans
                (lss_run_id, ingest_post_id,
                 ctx_kind, text,
                 start_token, end_token)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                lss_run_id,
                ingest_post_id,
                ctx_kind,
                text,
                start_token,
                end_token,
            ),
        )
