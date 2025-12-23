from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, date, time, timezone
from typing import List, Optional

from facebook_scraper import get_posts

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
            if data.get("source_kind") != "FACEBOOK":
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

def fetch_posts(
    start_date: str,
    end_date: Optional[str] = None,
    aliases: Optional[List[str]] = None,
    source_name: Optional[List[str]] = None,
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
        logger.warning("No active Facebook sources matched fetch criteria")
        return 0

    inserted = 0

    with sqlite3.connect(_DB_FILE) as conn:
        for cfg in sources:
            logger.info("Fetching Facebook posts for %s", cfg.source_name)

            translate = cfg.source_lang != "en"
            translator = MarianTranslator() if translate else None

            for post in get_posts(cfg.source_name):
                raw_text = (post.get("text") or "").strip()
                if not raw_text:
                    continue

                published = post.get("time")
                if not isinstance(published, datetime):
                    continue

                published = published.astimezone(UTC)
                if published < start_dt or published > end_dt:
                    continue

                text = raw_text
                lang = cfg.source_lang

                if translate:
                    try:
                        text = translator.translate(raw_text, source_lang=lang)
                        lang = "en"
                    except Exception:
                        continue

                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO ingest_posts
                    (source, publisher, source_post_id,
                     alias, lang, published_at, fetched_at, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "facebook",
                        cfg.source_name,
                        post.get("post_id"),
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
