# src/sitrepc2/lss/persist.py

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from sitrepc2.config.paths import records_path as records_db_path
from sitrepc2.lss.lss_scoping import (
    LSSRoleCandidate,
    LSSLocationSeries,
    LSSContextHint,
)

UTC = timezone.utc


# ---------------------------------------------------------------------
# CONNECTION
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
# RUNS
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
            "UPDATE lss_runs SET completed_at = ? WHERE id = ?",
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
) -> int:
    with _connection() as con:
        cur = con.execute(
            """
            INSERT INTO lss_sections
                (lss_run_id, ingest_post_id, text, ordinal)
            VALUES (?, ?, ?, ?)
            """,
            (lss_run_id, ingest_post_id, text, ordinal),
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
    rc: LSSRoleCandidate,
) -> None:
    with _connection() as con:
        con.execute(
            """
            INSERT INTO lss_role_candidates
                (lss_event_id, source, role_kind,
                 text, start_token, end_token,
                 match_type, negated, uncertain,
                 involves_coreference, similarity,
                 explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lss_event_id,
                "HOLMES",
                rc.role_kind,
                rc.text,
                rc.start_token,
                rc.end_token,
                None,
                int(rc.negated),
                int(rc.uncertain),
                int(rc.involves_coreference),
                rc.similarity,
                rc.explanation,
            ),
        )


# ---------------------------------------------------------------------
# LOCATION SERIES
# ---------------------------------------------------------------------

def persist_location_series(
    *,
    lss_event_id: int,
    series: LSSLocationSeries,
) -> dict[int, int]:
    with _connection() as con:
        cur = con.execute(
            """
            INSERT INTO lss_location_series
                (lss_event_id, start_token, end_token)
            VALUES (?, ?, ?)
            """,
            (lss_event_id, series.start_token, series.end_token),
        )
        series_db_id = int(cur.lastrowid)

        item_map: dict[int, int] = {}

        for item in series.items:
            cur = con.execute(
                """
                INSERT INTO lss_location_items
                    (series_id, text, start_token, end_token, ordinal)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    series_db_id,
                    item.text,
                    item.start_token,
                    item.end_token,
                    item.item_id,
                ),
            )
            item_map[item.item_id] = int(cur.lastrowid)

        return item_map


# ---------------------------------------------------------------------
# CONTEXT HINTS (GAZETTEER ONLY)
# ---------------------------------------------------------------------

def persist_context_hint(
    *,
    lss_run_id: int,
    hint: LSSContextHint,
    series_id_map: dict[int, int],
    item_id_map: dict[int, int],
    event_id_map: dict[int, int],
    section_id_map: dict[int, int],
) -> None:
    if hint.source != "GAZETTEER":
        return

    if hint.scope == "SERIES":
        target_id = series_id_map.get(hint.target_id)
    elif hint.scope == "LOCATION":
        target_id = item_id_map.get(hint.target_id)
    elif hint.scope == "EVENT":
        target_id = event_id_map.get(hint.target_id)
    elif hint.scope == "SECTION":
        target_id = section_id_map.get(hint.target_id)
    else:  # POST
        target_id = None

    with _connection() as con:
        con.execute(
            """
            INSERT INTO lss_context_hints
                (lss_run_id, ctx_kind, text,
                 start_token, end_token,
                 scope, target_id, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lss_run_id,
                hint.ctx_kind,
                hint.text,
                hint.start_token,
                hint.end_token,
                hint.scope,
                target_id,
                "GAZETTEER",
            ),
        )
