from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, date, time, timezone, timedelta
from pathlib import Path
from typing import AsyncIterator, Optional, List

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl import types

UTC = timezone.utc
logger = logging.getLogger(__name__)
load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DOTPATH = Path.home() / ".sitrepc2"
SOURCES_FILE = DOTPATH / "sources.jsonl"
DB_FILE = DOTPATH / "records.db"

# ---------------------------------------------------------------------------
# Bootstrap data
# ---------------------------------------------------------------------------

BOOTSTRAP_SOURCES = [
    {"channel_name": "mod_russia_en", "alias": "Russia", "channel_lang": "en", "active": True, "source_kind": "TELEGRAM"},
    {"channel_name": "GeneralStaffZSU", "alias": "Ukraine", "channel_lang": "uk", "active": True, "source_kind": "TELEGRAM"},
    {"channel_name": "deepstatemap", "alias": "DeepState", "channel_lang": "uk", "active": False, "source_kind": "TELEGRAM"},
    {"channel_name": "rybar_in_english", "alias": "Rybar", "channel_lang": "ru", "active": False, "source_kind": "TELEGRAM"},
]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ChannelConfig:
    channel_name: str
    alias: str
    channel_lang: str
    active: bool
    source_kind: str

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _ensure_dotpath() -> None:
    DOTPATH.mkdir(parents=True, exist_ok=True)


def _ensure_sources_file() -> None:
    if SOURCES_FILE.exists():
        return

    with SOURCES_FILE.open("w", encoding="utf-8") as f:
        for row in BOOTSTRAP_SOURCES:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    logger.info("Created default sources.jsonl at %s", SOURCES_FILE)


def _load_sources() -> List[ChannelConfig]:
    out: List[ChannelConfig] = []
    with SOURCES_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("source_kind") != "TELEGRAM":
                continue
            out.append(ChannelConfig(**data))
    return out


def _ensure_db() -> None:
    if DB_FILE.exists():
        return

    conn = sqlite3.connect(DB_FILE)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ingest_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            publisher TEXT NOT NULL,
            source_post_id TEXT NOT NULL,
            alias TEXT NOT NULL,
            lang TEXT NOT NULL,
            published_at TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            text TEXT NOT NULL,
            UNIQUE (source, publisher, source_post_id)
        );
        """
    )
    conn.commit()
    conn.close()

    logger.info("Created records.db with ingest_posts table")


def _load_telegram_credentials() -> tuple[int, str, str]:
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError("API_ID and API_HASH must be set")

    session_name = os.getenv("TELEGRAM_SESSION_NAME", "sitrepc2")
    return int(api_id), api_hash, session_name


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
# Telegram iteration
# ---------------------------------------------------------------------------

async def _iter_messages(
    client: TelegramClient,
    entity: types.TypeInputPeer,
    start_dt: datetime,
    end_dt: datetime,
) -> AsyncIterator[types.Message]:

    offset_dt = end_dt + timedelta(seconds=1)
    async for msg in client.iter_messages(entity, offset_date=offset_dt):
        if not msg.date:
            continue
        msg_dt = msg.date.astimezone(UTC)
        if msg_dt < start_dt:
            break
        if msg_dt > end_dt:
            continue
        yield msg

# ---------------------------------------------------------------------------
# Core ingest
# ---------------------------------------------------------------------------

async def _fetch_async(
    start_date: str,
    end_date: Optional[str],
    aliases: Optional[List[str]],
) -> int:

    _ensure_dotpath()
    _ensure_sources_file()
    _ensure_db()

    api_id, api_hash, session_name = _load_telegram_credentials()
    start_dt, end_dt = _parse_date_range(start_date, end_date)

    channels = [
        c for c in _load_sources()
        if c.active and (aliases is None or c.alias.lower() in {a.lower() for a in aliases})
    ]

    inserted = 0
    conn = sqlite3.connect(DB_FILE)

    async with TelegramClient(session_name, api_id, api_hash) as client:
        for cfg in channels:
            try:
                entity = await client.get_entity(cfg.channel_name)
            except RPCError as e:
                logger.warning("Skipping %s: %s", cfg.channel_name, e)
                continue

            async for msg in _iter_messages(client, entity, start_dt, end_dt):
                text = (msg.message or "").strip()
                if not text:
                    continue

                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO ingest_posts
                        (source, publisher, source_post_id,
                         alias, lang, published_at, fetched_at, text)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "telegram",
                            cfg.channel_name,
                            str(msg.id),
                            cfg.alias,
                            cfg.channel_lang,
                            _utc_iso(msg.date),
                            _utc_iso(datetime.now(UTC)),
                            text,
                        ),
                    )
                    if conn.total_changes:
                        inserted += 1
                except sqlite3.Error as e:
                    logger.error("DB error: %s", e)

    conn.commit()
    conn.close()
    return inserted


def fetch_posts(
    start_date: str,
    end_date: Optional[str] = None,
    aliases: Optional[List[str]] = None,
) -> int:
    return asyncio.run(_fetch_async(start_date, end_date, aliases))
