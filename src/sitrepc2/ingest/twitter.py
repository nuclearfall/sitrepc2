from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
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
    channel_name: str
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


def _utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Core ingest
# ---------------------------------------------------------------------------

async def _fetch_async(
    translator: Optional[MarianTranslator] = None,
) -> int:
    _require_records_db()
    sources = _load_sources()

    if not sources:
        logger.warning("No active Twitter sources")
        return 0

    inserted = 0

    with sqlite3.connect(_DB_FILE) as conn:
        for cfg in sources:
            logger.info("Fetching tweets for @%s", cfg.channel_name)

            tweets = []

            c = twint.Config()
            c.Username = cfg.channel_name
            c.Store_object = True
            c.Hide_output = True

            twint.output.tweets_list = []
            await twint.run.Search(c)

            tweets = twint.output.tweets_list

            for t in tweets:
                raw_text = t.tweet.strip()
                if not raw_text:
                    continue

                lang = t.lang or cfg.channel_lang

                if translator and lang != "en":
                    try:
                        text = translator.translate(raw_text, source_lang=lang)
                        lang = "en"
                    except Exception as e:
                        logger.warning("Translation failed: %s", e)
                        continue
                else:
                    if lang != "en":
                        continue
                    text = raw_text

                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO ingest_posts
                    (source, publisher, source_post_id,
                     alias, lang, published_at, fetched_at, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "twitter",
                        cfg.channel_name,
                        str(t.id),
                        cfg.alias,
                        lang,
                        _utc_iso(t.datestamp),
                        _utc_iso(datetime.now(UTC).timestamp()),
                        text,
                    ),
                )

                if cur.rowcount == 1:
                    inserted += 1

        conn.commit()

    return inserted


def fetch_posts(
    translate: bool = False,
) -> int:
    translator = MarianTranslator() if translate else None
    return asyncio.run(_fetch_async(translator))
