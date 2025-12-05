# src/modmymap/ingest/telegram_window.py
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Final

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.tl import functions, types

logger = logging.getLogger(__name__)
load_dotenv()

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")

# How aggressively we translate
MIN_TRANSLATION_LENGTH = 40  # characters; tune as desired
TRANSLATE_SLEEP_SECONDS = 5.0  # polite delay between TranslateTextRequest calls
MAX_TRANSLATION_RETRIES = 5

# ---------------------------------------------------------------------------
# Channel config
# ---------------------------------------------------------------------------


@dataclass
class ChannelConfig:
    channel_name: str
    alias: str
    channel_lang: str
    active: bool

    @classmethod
    def from_json(cls, data: dict) -> ChannelConfig:
        return cls(
            channel_name=data["channel_name"],
            alias=data.get("alias", data["channel_name"]),
            channel_lang=data.get("channel_lang", "en"),
            active=bool(data.get("active", False)),
        )


HARDCODED_CHANNELS: list[ChannelConfig] = [
    ChannelConfig(
        channel_name="mod_russia_en",
        alias="Russia",
        channel_lang="en",
        active=False,
    ),
    ChannelConfig(
        channel_name="GeneralStaffZSU",
        alias="Ukraine",
        channel_lang="uk",
        active=False,
    ),
    ChannelConfig(
        channel_name="militarysummary",
        alias="MS",
        channel_lang="en",
        active=False,
    ),
    ChannelConfig(
        channel_name="rybar_in_english",
        alias="Rybar",
        channel_lang="en",
        active=True,
    ),
]

# Phrases to keep posts for. Edit/extend as needed.
PHRASE_FILTERS: list[str] = [
    "Operational information as of",
    "on progress of special military operation as of",
    "Оперативна інформація станом на",
    "Coordinates:",
]

BASE_RETRY_SLEEP_SECONDS = 5.0  # adjust if needed

FRONTLINE_KEYWORDS: Final = ()

# Keywords/hashtags to *skip* (training / PR / recruitment) — currently unused
TRAINING_HASHTAGS: Final = (
    "#підготовказсу",
    "#підготовказсу2025",
)

TRAINING_PHRASES: Final = (
    "щодня вдосконалюють свої навички",
    "навички та вміння",
    "підготовка",
    "тренування",
    "як діяти в «урбані»",
    'як діяти в "урбані"',
    "як врятувати побратима",
    "відділення комунікацій",
    "пресслужба",
    "прес-служба",
)

RECRUITMENT_PHRASES: Final = (
    "приєднуйтесь до сил оборони",
    "разом переможемо",
    "слава україні",
)

TOPONYM_LIKE_RE = re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ']+(?:,|\b)")


class ProgressBar:
    def __init__(self, total: int, width: int = 30):
        self.total = max(total, 1)
        self.width = width
        self.count = 0

    def advance(self) -> None:
        self.count += 1
        filled = int(self.width * (self.count / self.total))
        bar = "█" * filled + "░" * (self.width - filled)
        print(f"\r[ {bar} ] {self.count}/{self.total}", end="", flush=True)

    def finish(self) -> None:
        print()  # move to next line


def should_translate_uk_post(text: str) -> bool:
    blacklist = RECRUITMENT_PHRASES + TRAINING_PHRASES + TRAINING_HASHTAGS
    lowered = text.lower()
    return not any(word.lower() in lowered for word in blacklist)


class TranslationFailed(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Filters & helpers
# ---------------------------------------------------------------------------


def _matches_phrase_filter(text: str) -> bool:
    """
    Return True if `text` contains any of the configured phrases (case-insensitive).
    """
    if not text:
        return False
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in PHRASE_FILTERS)


def _load_telegram_credentials() -> tuple[int, str, str]:
    """
    Load Telegram API credentials from environment variables.

    Required:
      - API_ID      (int)
      - API_HASH    (str)

    Optional:
      - TELEGRAM_SESSION_NAME (str, defaults to "modmymap")
    """
    api_id_raw = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")

    if api_id_raw is None or api_hash is None:
        raise RuntimeError("API_ID and API_HASH must be set in the environment")

    api_id = int(api_id_raw)
    session_name = os.getenv("TELEGRAM_SESSION_NAME", "modmymap")
    return api_id, api_hash, session_name


def _parse_date_range(
    start_date: str | date,
    end_date: str | date | None,
) -> tuple[datetime, datetime]:
    """
    Accepts either ISO strings or datetime.date objects.
    Returns an inclusive UTC datetime range.
    """
    if isinstance(start_date, date):
        start_d = start_date
    else:
        start_d = date.fromisoformat(start_date)

    if end_date is None:
        end_d = start_d
    else:
        if isinstance(end_date, date):
            end_d = end_date
        else:
            end_d = date.fromisoformat(end_date)

    if end_d < start_d:
        raise ValueError("end_date must be >= start_date")

    start_dt = datetime.combine(start_d, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end_d, time.max, tzinfo=UTC)
    return start_dt, end_dt


def _utc_iso(dt: datetime) -> str:
    """
    Normalize datetime to UTC and format as ISO 8601 with 'Z' suffix.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")


def _output_path_for_today(base_dir: Path | None = None) -> Path:
    """
    Build today's interim posts path:
      data/interim/YYYY/YYYY-MM/YYYY-MM-DD/posts.jsonl
    """
    today = date.today()
    if base_dir is None:
        base_dir = Path("data") / "interim"

    year_dir = base_dir / f"{today.year}"
    month_dir = year_dir / f"{today.year}-{today.month:02d}"
    day_dir = month_dir / today.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir / "posts.jsonl"


def _ensure_output_path(out_path: Path | None) -> Path:
    """
    Use the provided out_path, or default to the standard interim path.
    Ensures parent directories exist.
    """
    if out_path is None:
        out_path = _output_path_for_today()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return out_path


def _load_channels_from_file(path: Path) -> list[ChannelConfig]:
    channels: list[ChannelConfig] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            cfg = ChannelConfig.from_json(data)
            if cfg.active:
                channels.append(cfg)
    return channels


async def _iter_messages_in_range(
    client: TelegramClient,
    entity: types.TypeInputPeer | str,
    start_dt: datetime,
    end_dt: datetime,
) -> AsyncIterator[types.Message]:
    """
    Yield messages for `entity` with date in [start_dt, end_dt] (UTC).

    We iterate backwards from (end_dt + 1 second) until we drop below start_dt.
    """
    offset_dt = end_dt + timedelta(seconds=1)

    async for msg in client.iter_messages(entity, offset_date=offset_dt):
        if msg.date is None:
            continue

        msg_dt = msg.date
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=UTC)
        else:
            msg_dt = msg_dt.astimezone(UTC)

        if msg_dt < start_dt:
            break
        if msg_dt > end_dt:
            continue

        yield msg


async def _translate_message_text(
    client: TelegramClient,
    entity: types.TypeInputPeer | str,
    message: types.Message,
    to_lang: str = "en",
) -> str | None:
    original_text = (message.message or "").strip()
    if not original_text:
        return None

    if len(original_text) < MIN_TRANSLATION_LENGTH:
        logger.debug(
            "Skipping translation for short message %s (len=%d < %d)",
            message.id,
            len(original_text),
            MIN_TRANSLATION_LENGTH,
        )
        return None

    last_error: Exception | None = None

    for attempt in range(1, MAX_TRANSLATION_RETRIES + 1):
        try:
            logger.debug(
                "Translating message %s (attempt %d/%d)",
                message.id,
                attempt,
                MAX_TRANSLATION_RETRIES,
            )

            result = await client(
                functions.messages.TranslateTextRequest(
                    peer=entity,
                    id=[message.id],
                    to_lang=to_lang,
                )
            )

            if getattr(result, "result", None):
                translated = result.result[0].text or original_text
            else:
                translated = original_text

            return translated

        except FloodWaitError as e:
            last_error = e
            required = e.seconds

            logger.warning(
                "FloodWaitError for message %s (attempt %d/%d): "
                "%s seconds required by Telegram.",
                message.id,
                attempt,
                MAX_TRANSLATION_RETRIES,
                required,
            )

            if attempt == MAX_TRANSLATION_RETRIES:
                break

            await asyncio.sleep(required + 1)

        except RPCError as e:
            last_error = e
            logger.warning(
                "RPCError for message %s on attempt %d/%d: %s",
                message.id,
                attempt,
                MAX_TRANSLATION_RETRIES,
                e,
            )

            if attempt == MAX_TRANSLATION_RETRIES:
                break

            await asyncio.sleep(BASE_RETRY_SLEEP_SECONDS * attempt)

        except Exception as e:
            last_error = e
            logger.warning(
                "Unexpected translation error for message %s on attempt %d/%d: %s",
                message.id,
                attempt,
                MAX_TRANSLATION_RETRIES,
                e,
            )

            if attempt == MAX_TRANSLATION_RETRIES:
                break

            await asyncio.sleep(BASE_RETRY_SLEEP_SECONDS * attempt)

    raise TranslationFailed(
        f"Failed to translate message {message.id} after "
        f"{MAX_TRANSLATION_RETRIES} attempts. last_error={last_error!r}"
    )


def _extract_message_text(msg: types.Message) -> str:
    """
    Get the text content of a message (skipping service/empty messages).
    """
    text = msg.message or getattr(msg, "raw_text", "") or ""
    return text.strip()


# ---------------------------------------------------------------------------
# Core async implementation
# ---------------------------------------------------------------------------


async def _ingest_telegram_window_async(
    start_date: str,
    end_date: str | None,
    out_path: Path | None = None,
    channels_path: Path | None = None,
) -> tuple[Path, list[dict]]:
    """
    Core async implementation.

    Now:
      - Pre-filters messages by PHRASE_FILTERS on the *raw* text.
      - For non-English channels, only those pre-filtered messages are
        considered for translation and counted in the progress bar.
    """
    api_id, api_hash, session_name = _load_telegram_credentials()
    start_dt, end_dt = _parse_date_range(start_date, end_date)

    # Determine channels: file overrides hard-coded list if given
    if channels_path is not None:
        channels = _load_channels_from_file(channels_path)
        if not channels:
            logger.warning(
                "No active channels found in %s; falling back to HARDCODED_CHANNELS",
                channels_path,
            )
            channels = [cfg for cfg in HARDCODED_CHANNELS if cfg.active]
    else:
        channels = [cfg for cfg in HARDCODED_CHANNELS if cfg.active]

    if not channels:
        logger.info("No active channels in configuration.")

    output_path = _ensure_output_path(out_path)

    logger.info(
        "Ingesting Telegram window %s → %s into %s",
        start_dt.isoformat(),
        end_dt.isoformat(),
        output_path,
    )

    records: list[dict] = []

    async with TelegramClient(session_name, api_id, api_hash) as client:
        with output_path.open("a", encoding="utf-8") as out_f:
            for cfg in channels:
                logger.info(
                    "Fetching from channel %s (alias=%s, lang=%s)",
                    cfg.channel_name,
                    cfg.alias,
                    cfg.channel_lang,
                )

                try:
                    entity = await client.get_entity(cfg.channel_name)
                except RPCError as exc:
                    logger.error(
                        "Failed to resolve channel %s: %s",
                        cfg.channel_name,
                        exc,
                    )
                    continue

                lang = cfg.channel_lang.lower()

                # --------------------------------------------------
                # ENGLISH CHANNELS — single pass, phrase filter only
                # --------------------------------------------------
                if lang == "en":
                    async for msg in _iter_messages_in_range(
                        client=client,
                        entity=entity,
                        start_dt=start_dt,
                        end_dt=end_dt,
                    ):
                        text_orig = _extract_message_text(msg)
                        if not text_orig:
                            continue

                        # Pre-filter on raw text (Russian MoD phrase appears
                        # directly in original text).
                        if not _matches_phrase_filter(text_orig):
                            continue

                        text_en = text_orig
                        raw_text = None

                        record = {
                            "source": "telegram",
                            "channel": cfg.channel_name,
                            "alias": cfg.alias,
                            "channel_lang": cfg.channel_lang,
                            "post_id": msg.id,
                            "published_at": _utc_iso(msg.date),
                            "fetched_at": _utc_iso(datetime.now(UTC)),
                            "raw_text": raw_text,
                            "text": text_en,
                        }

                        out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                        records.append(record)

                    # Done with this channel
                    continue

                # --------------------------------------------------
                # NON-ENGLISH CHANNELS (e.g. GeneralStaffZSU, lang='uk')
                # First pass: find which messages *both* match the
                # phrase filter and are worth translating.
                # --------------------------------------------------
                translate_candidates: set[int] = set()

                async for msg in _iter_messages_in_range(
                    client=client,
                    entity=entity,
                    start_dt=start_dt,
                    end_dt=end_dt,
                ):
                    text_orig = _extract_message_text(msg)
                    if not text_orig:
                        continue

                    # PRE-FILTER by PHRASE_FILTERS on RAW TEXT
                    # (e.g. Ukrainian "Оперативна інформація станом на").
                    if not _matches_phrase_filter(text_orig):
                        continue

                    if lang == "uk":
                        if not should_translate_uk_post(text_orig):
                            continue
                        translate_candidates.add(msg.id)
                    else:
                        # Other non-EN languages, if you ever add them.
                        translate_candidates.add(msg.id)

                total_to_translate = len(translate_candidates)
                progress = ProgressBar(total_to_translate if total_to_translate > 0 else 1)

                logger.info(
                    "Channel %s: %d messages match sitrep phrases and require translation.",
                    cfg.channel_name,
                    total_to_translate,
                )

                # --------------------------------------------------
                # SECOND PASS — real ingestion, only for candidates
                # --------------------------------------------------
                async for msg in _iter_messages_in_range(
                    client=client,
                    entity=entity,
                    start_dt=start_dt,
                    end_dt=end_dt,
                ):
                    # Only touch messages we decided were interesting in pass 1.
                    if msg.id not in translate_candidates:
                        continue

                    text_orig = _extract_message_text(msg)
                    if not text_orig:
                        continue

                    try:
                        text_en = await _translate_message_text(
                            client=client,
                            entity=entity,
                            message=msg,
                            to_lang="en",
                        )
                        if text_en is None:
                            progress.advance()
                            continue

                        raw_text = text_orig
                        progress.advance()

                    except TranslationFailed:
                        progress.finish()
                        raise

                    # You *can* re-check the phrase filter on text_en here,
                    # but given the fixed formulaic headers, it's probably
                    # redundant. Keeping the record unconditionally for
                    # all candidates:
                    record = {
                        "source": "telegram",
                        "channel": cfg.channel_name,
                        "alias": cfg.alias,
                        "channel_lang": cfg.channel_lang,
                        "post_id": msg.id,
                        "published_at": _utc_iso(msg.date),
                        "fetched_at": _utc_iso(datetime.now(UTC)),
                        "raw_text": raw_text,
                        "text": text_en,
                    }

                    out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    records.append(record)

                progress.finish()

    logger.info("Ingestion complete, output written to %s", output_path)
    return output_path, records


# ---------------------------------------------------------------------------
# Public sync wrapper
# ---------------------------------------------------------------------------


def fetch_posts(
    start_date: str,
    end_date: str | None = None,
    channels_path: Path | None = None,
    out_path: Path | None = None,
) -> tuple[Path, list[dict]]:
    """
    Synchronous wrapper around the async ingest function.
    """
    return asyncio.run(
        _ingest_telegram_window_async(
            start_date=start_date,
            end_date=end_date,
            out_path=out_path,
            channels_path=channels_path,
        )
    )


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and translate Telegram posts in a date window."
    )
    parser.add_argument(
        "-s",
        "--start",
        required=True,
        help="Start date (YYYY-MM-DD, inclusive).",
    )
    parser.add_argument(
        "-e",
        "--end",
        help="End date (YYYY-MM-DD, inclusive). Defaults to start date if omitted.",
    )
    parser.add_argument(
        "-i",
        "--import",
        dest="import_path",
        help=(
            "Optional path to channels JSONL file. "
            "If provided, overrides the hard-coded channel list."
        ),
    )
    parser.add_argument(
        "-o",
        "--out",
        dest="out_path",
        help=(
            "Optional JSONL output path. "
            "If omitted, uses data/interim/YYYY/YYYY-MM/YYYY-MM-DD/posts.jsonl."
        ),
    )

    args = parser.parse_args(argv)

    start_date = args.start
    end_date = args.end

    channels_path: Path | None = Path(args.import_path) if args.import_path else None
    out_path: Path | None = Path(args.out_path) if args.out_path else None

    output_path, records = fetch_posts(
        start_date=start_date,
        end_date=end_date,
        channels_path=channels_path,
        out_path=out_path,
    )

    print(f"Wrote {len(records)} records to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
