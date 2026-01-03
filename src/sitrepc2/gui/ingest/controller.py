from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any

from sitrepc2.config.paths import records_path, sources_path


# ============================================================================
# ENUMS
# ============================================================================

class IngestPostState(str, Enum):
    RAW = "RAW"
    LSS_RUNNING = "LSS_RUNNING"
    NO_EVENTS = "NO_EVENTS"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    COMMITTED = "COMMITTED"


# ============================================================================
# DATA TRANSFER OBJECTS (GUI-FACING)
# ============================================================================

@dataclass(frozen=True, slots=True)
class SourceInfo:
    source_name: str
    alias: str
    source_kind: str
    source_lang: str
    active: bool


@dataclass(frozen=True, slots=True)
class IngestPostFilter:
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    source: Optional[str] = None
    publisher: Optional[str] = None
    alias: Optional[str] = None
    lang: Optional[str] = None
    state: Optional[IngestPostState] = None


@dataclass(frozen=True, slots=True)
class IngestPostRow:
    post_id: int
    alias: str
    source: str
    publisher: str
    lang: str
    published_at: str
    fetched_at: str
    text_snippet: str
    state: IngestPostState
    event_count: int


@dataclass(frozen=True, slots=True)
class IngestPostDetail:
    post_id: int
    source: str
    publisher: str
    source_post_id: str
    alias: str
    lang: str
    published_at: str
    fetched_at: str
    text: str
    state: IngestPostState
    event_count: int


# ============================================================================
# CONTROLLER
# ============================================================================

class IngestController:
    """
    Controller for ingest workspace.

    - Reads ingest_posts
    - Reads LSS state
    - Reads DOM commit status (if present)
    - Reads source registry (JSONL)
    - NEVER mutates ingest, LSS, or DOM tables
    """

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def get_sources(self) -> List[SourceInfo]:
        sources: List[SourceInfo] = []

        path = sources_path()
        if not path.exists():
            return sources

        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue

                data = json.loads(line)

                sources.append(
                    SourceInfo(
                        source_name=data["source_name"],
                        alias=data["alias"],
                        source_kind=data["source_kind"],
                        source_lang=data["source_lang"],
                        active=bool(data["active"]),
                    )
                )

        return sources

    # ------------------------------------------------------------------
    # Posts (table)
    # ------------------------------------------------------------------

    def query_posts(self, flt: IngestPostFilter) -> List[IngestPostRow]:
        con = sqlite3.connect(records_path())
        con.row_factory = sqlite3.Row

        sql, params = self._build_query(flt)
        rows = con.execute(sql, params).fetchall()

        result: List[IngestPostRow] = []

        for row in rows:
            state, event_count = self._derive_state(con, row["id"])

            if flt.state is not None and state != flt.state:
                continue

            snippet = row["text"][:120].replace("\n", " ").strip()

            result.append(
                IngestPostRow(
                    post_id=row["id"],
                    alias=row["alias"],
                    source=row["source"],
                    publisher=row["publisher"],
                    lang=row["lang"],
                    published_at=row["published_at"],
                    fetched_at=row["fetched_at"],
                    text_snippet=snippet,
                    state=state,
                    event_count=event_count,
                )
            )

        con.close()
        return result

    # ------------------------------------------------------------------
    # Single post (detail)
    # ------------------------------------------------------------------

    def get_post(self, post_id: int) -> IngestPostDetail:
        con = sqlite3.connect(records_path())
        con.row_factory = sqlite3.Row

        row = con.execute(
            """
            SELECT
                id,
                source,
                publisher,
                source_post_id,
                alias,
                lang,
                published_at,
                fetched_at,
                text
            FROM ingest_posts
            WHERE id = :pid
            """,
            {"pid": post_id},
        ).fetchone()

        if row is None:
            con.close()
            raise KeyError(f"Ingest post {post_id} not found")

        state, event_count = self._derive_state(con, post_id)

        detail = IngestPostDetail(
            post_id=row["id"],
            source=row["source"],
            publisher=row["publisher"],
            source_post_id=row["source_post_id"],
            alias=row["alias"],
            lang=row["lang"],
            published_at=row["published_at"],
            fetched_at=row["fetched_at"],
            text=row["text"],
            state=state,
            event_count=event_count,
        )

        con.close()
        return detail

    # ============================================================================
    # INTERNALS
    # ============================================================================

    def _build_query(
        self, flt: IngestPostFilter
    ) -> tuple[str, Dict[str, Any]]:
        where = []
        params: Dict[str, Any] = {}

        if flt.from_date:
            where.append("published_at >= :from_date")
            params["from_date"] = flt.from_date

        if flt.to_date:
            where.append("published_at <= :to_date")
            params["to_date"] = flt.to_date + "T23:59:59"

        if flt.source:
            where.append("source = :source")
            params["source"] = flt.source

        if flt.publisher:
            where.append("publisher LIKE :publisher")
            params["publisher"] = f"%{flt.publisher}%"

        if flt.alias:
            where.append("alias LIKE :alias")
            params["alias"] = f"%{flt.alias}%"

        if flt.lang:
            where.append("lang = :lang")
            params["lang"] = flt.lang

        where_sql = ""
        if where:
            where_sql = "WHERE " + " AND ".join(where)

        sql = f"""
            SELECT
                id,
                source,
                publisher,
                source_post_id,
                alias,
                lang,
                published_at,
                fetched_at,
                text
            FROM ingest_posts
            {where_sql}
            ORDER BY published_at DESC
        """

        return sql, params

    # ------------------------------------------------------------------

    def _derive_state(
        self, con: sqlite3.Connection, post_id: int
    ) -> tuple[IngestPostState, int]:

        # DOM commit check (optional table)
        try:
            dom = con.execute(
                """
                SELECT status
                FROM dom_posts
                WHERE post_id = :pid
                """,
                {"pid": post_id},
            ).fetchone()
        except sqlite3.OperationalError:
            dom = None

        if dom and dom["status"] == "COMMITTED":
            count = self._count_events(con, post_id)
            return IngestPostState.COMMITTED, count

        # LSS runs
        run = con.execute(
            """
            SELECT completed_at
            FROM lss_runs
            WHERE ingest_post_id = :pid
            ORDER BY started_at DESC
            LIMIT 1
            """,
            {"pid": post_id},
        ).fetchone()

        if run is None:
            return IngestPostState.RAW, 0

        if run["completed_at"] is None:
            return IngestPostState.LSS_RUNNING, 0

        count = self._count_events(con, post_id)
        if count == 0:
            return IngestPostState.NO_EVENTS, 0

        return IngestPostState.READY_FOR_REVIEW, count

    # ------------------------------------------------------------------

    def _count_events(
        self, con: sqlite3.Connection, post_id: int
    ) -> int:
        row = con.execute(
            """
            SELECT COUNT(*)
            FROM lss_events
            WHERE ingest_post_id = :pid
            """,
            {"pid": post_id},
        ).fetchone()

        return int(row[0]) if row else 0
