from __future__ import annotations

import json
import sqlite3

from datetime import datetime
from typing import List

from sitrepc2.config.paths import sources_path, records_path
from sitrepc2.gui.ingest.typedefs import (
    SourceEntry,
    IngestPostEntry,
    IngestState,
)


def load_ingest_posts() -> List[IngestPostEntry]:
    """
    Load ingest posts from records.db for GUI use.

    Pure read adapter:
    - no filtering
    - no mutation
    - no side effects
    """

    with sqlite3.connect(records_path()) as con:
        con.row_factory = sqlite3.Row

        rows = con.execute(
            """
            SELECT
                p.id,
                p.source,
                p.publisher,
                p.alias,
                p.lang,
                p.published_at,
                p.text,
                EXISTS (
                    SELECT 1
                    FROM lss_runs r
                    WHERE r.ingest_post_id = p.id
                      AND r.completed_at IS NOT NULL
                ) AS extracted
            FROM ingest_posts p
            ORDER BY p.published_at DESC
            """
        ).fetchall()

    posts: List[IngestPostEntry] = []

    for row in rows:
        posts.append(
            IngestPostEntry(
                post_id=row["id"],
                source=row["source"],
                publisher=row["publisher"],
                alias=row["alias"],
                lang=row["lang"],
                published_at=datetime.fromisoformat(
                    row["published_at"].replace("Z", "+00:00")
                ),
                text=row["text"],
                state=(
                    IngestState.EXTRACTED
                    if row["extracted"]
                    else IngestState.INGESTED
                ),
            )
        )

    return posts




def load_sources() -> List[SourceEntry]:
    """
    Load sources from sources.jsonl.

    This is a pure read adapter:
    - no validation beyond presence
    - no mutation
    - no persistence side effects
    """

    path = sources_path()
    if not path.exists():
        return []

    sources: List[SourceEntry] = []

    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Invalid JSON in sources.jsonl at line {line_no}"
                ) from exc

            sources.append(
                SourceEntry(
                    source_name=str(record.get("source_name", "")),
                    alias=str(record.get("alias", "")),
                    source_kind=str(record.get("source_kind", "")),
                    lang=str(record.get("source_lang", "")),
                    active=bool(record.get("active", False)),
                )
            )

    return sources
