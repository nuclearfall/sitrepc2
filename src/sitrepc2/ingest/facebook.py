from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

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
    channel_name: str      # page or group name
    alias: str
    channel_lang: str
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


# ---------------------------------------------------------------------------
# Core ingest
# ---------------------------------------------------------------------------

def fetch_posts(limit: int = 50) -> int:
    """
    Fetch Facebook posts and ingest into records.db.

    Translation is ALWAYS applied for non-English sources.
    """
    _require_records_db()
    sources = _load_sources()

    if not sources:
        logger.warning("No active Facebook sources")
        return 0

    translator = MarianTranslator()
    inserted = 0

    with sqlite3.connect(_DB_FILE) as conn:
        for cfg in sources:
            logger.info("Fetching Facebook posts for %s", cfg.channel_name)

            for post in get_posts(cfg.channel_name, pages=limit):
                raw_text = post.get("text") or ""
                if not raw_text.strip():
                    continue

                lang = cfg.channel_lang

                if lang != "en":
                    try:
                        text = translator.translate(raw_text, source_lang=lang)
                        lang = "en"
                    except Exception as e:
                        logger.warning("Translation failed: %s", e)
                        continue
                else:
                    text = raw_text

                published = post.get("time") or datetime.now(UTC)

                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO ingest_posts
                    (source, publisher, source_post_id,
                     alias, lang, published_at, fetched_at, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "facebook",
                        cfg.channel_name,
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
