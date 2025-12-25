from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, date, time, timezone
from typing import List, Optional

import twint

from sitrepc2.config.paths import records_path, sources_path
from sitrepc2.ingest.translate import MarianTranslator

UTC = timezone.utc
logger = logging.getLogger(__name__)

_SOURCES_FILE = sources_path()
_DB_FILE = records_path()

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SourceConfig:
    source_name: str
    alias: str
    source_lang: str
    active: bool
    source_kind: str

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _load_sources() -> List[SourceConfig]:
    out: List[SourceConfig] = []
    with _SOURCES_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("source_kind") != "TWITTER":
                continue
            if not data.get("active", False):
                continue
            out.append(SourceConfig(**data))
    return out


def _require_records_db() -> None:
    if not _DB_FILE.exists():
        raise RuntimeError(
            f"records.db not found at {_DB_FILE}. Run `sitrepc2 init` first."
        )


def _utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_date_range(start: str, end: Optional[str]) -> tuple[datetime, datetime]:
    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end) if end else start_d
    return (
        datetime.combine(start_d, time.min, tzinfo=UTC),
        datetime.combine(end_d, time.max, tzinfo=UTC),
    )

# ---------------------------------------------------------------------------
# Core ingest
# ---------------------------------------------------------------------------

async def _fetch_async(
    start_date: str,
    end_date: Optional[str],
    aliases: Optional[List[str]],
    source_name: Optional[List[str]],
) -> int:

    _require_records_db()

    start_dt, end_dt = _parse_date_range(start_date, end_date)
    alias_filter = {a.lower() for a in aliases} if aliases else None
    source_filter = {s.lower() for s in source_name} if source_name else None

    sources = [
        s for s in _load_sources()
        if (
            (source_filter and s.source_name.lower() in source_filter)
            or (not source_filter and alias_filter and s.source_name.lower() in alias_filter)
            or (not source_filter and not alias_filter)
        )
    ]

    if not sources:
        logger.warning("No active Twitter sources matched fetch criteria")
        return 0

    inserted = 0

    with sqlite3.connect(_DB_FILE) as conn:
        for cfg in sources:
            logger.info("Fetching tweets for @%s", cfg.source_name)

            translate = cfg.source_lang != "en"
            translator = MarianTranslator() if translate else None

            c = twint.Config()
            c.Username = cfg.source_name
            c.Store_object = True
            c.Hide_output = True

            twint.output.tweets_list = []
            await twint.run.Search(c)

            for t in twint.output.tweets_list:
                raw_text = t.tweet
                if not raw_text.strip():
                    continue

                published = datetime.fromtimestamp(t.datestamp, tz=UTC)
                if published < start_dt or published > end_dt:
                    continue

                text = raw_text
                lang = cfg.source_lang

                if translate:
                    try:
                        text = translator.translate(raw_text, source_lang=lang)
                        lang = "en"
                    except Exception as e:
                        logger.warning(
                            "Translation failed for @%s (%s): %s",
                            cfg.source_name,
                            lang,
                            e,
                        )
                        continue

                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO ingest_posts
                    (source, publisher, source_post_id,
                     alias, lang, published_at, fetched_at, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "twitter",
                        cfg.source_name,
                        str(t.id),
                        cfg.alias,
                        lang,
                        _utc_iso(published),
                        _utc_iso(datetime.now(UTC)),
                        text,
                    ),
                )

                if cur.rowcount == 1:
                    inserted += 1

        conn.commit()

    return inserted


def fetch_posts(
    start_date: str,
    end_date: Optional[str] = None,
    aliases: Optional[List[str]] = None,
    source_name: Optional[List[str]] = None,
) -> int:
    return asyncio.run(
        _fetch_async(start_date, end_date, aliases, source_name)
    )
