# src/sitrepc2/lss/persist.py

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from sitrepc2.config.paths import records_path as records_db_path

UTC = timezone.utc


# ---------------------------------------------------------------------
# Connection / transaction helpers
# ---------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@contextmanager
def _connection() -> sqlite3.Connection:
    con = sqlite3.connect(records_db_path())
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


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
    with _connection() as con:
        cur = con.execute(
            """
            INSERT INTO lss_runs
                (ingest_post_id, started_at, engine, engine_version, model)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ingest_post_id, _utc_now_iso(), engine, engine_version, model),
        )
        return int(cur.lastrowid)


def complete_lss_run(lss_run_id: int) -> None:
    with _connection() as con:
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
    with _connection() as con:
        cur = con.execute(
            """
            INSERT INTO lss_sections
                (lss_run_id, ingest_post_id, text,
                 start_token, end_token, ordinal)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (lss_run_id, ingest_post_id, text, start_token, end_token, ordinal),
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
    with _connection() as con:
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
    source: str,                # 'HOLMES' | 'LSS'
    role_kind: str,             # ACTOR / ACTION / LOCATION / RAW
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
    with _connection() as con:
        con.execute(
            """
            INSERT INTO lss_role_candidates
                (lss_event_id, source, role_kind,
                 document_word, document_phrase,
                 start_token, end_token,
                 match_type, negated, uncertain,
                 involves_coreference, similarity,
                 explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lss_event_id,
                source,
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


def persist_holmes_word_matches(
    *,
    lss_event_id: int,
    word_matches: list,
) -> None:
    for wm in word_matches:
        persist_role_candidate(
            lss_event_id=lss_event_id,
            source="HOLMES",
            role_kind="RAW",
            document_word=wm.document_word,
            document_phrase=wm.document_phrase,
            start_token=wm.first_document_token_index,
            end_token=wm.last_document_token_index + 1,
            match_type=wm.match_type,
            negated=wm.negated,
            uncertain=wm.uncertain,
            involves_coreference=wm.involves_coreference,
            similarity=wm.similarity_measure,
            explanation=wm.explanation,
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
    with _connection() as con:
        con.execute(
            """
            INSERT INTO lss_context_spans
                (lss_run_id, ingest_post_id,
                 ctx_kind, text,
                 start_token, end_token)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (lss_run_id, ingest_post_id, ctx_kind, text, start_token, end_token),
        )
