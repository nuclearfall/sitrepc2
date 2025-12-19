from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from readability import Document

from sitrepc2.config.paths import records_path, sources_path
from sitrepc2.ingest.translate import MarianTranslator
from sitrepc2.ingest.date_extract import extract_published_at

UTC = timezone.utc
logger = logging.getLogger(__name__)

_SOURCES_FILE = sources_path()
_DB_FILE = records_path()

HEADERS = {
    "User-Agent": "sitrepc2/0.1 (OSINT ingestion)",
    "Accept-Language": "en",
}

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SourceConfig:
    channel_name: str    # Base URL
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
            if data.get("source_kind") != "HTTP":
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
# Scraping helpers
# ---------------------------------------------------------------------------

def _discover_links(base_url: str) -> Set[str]:
    """
    Discover candidate article URLs from a base page.
    Only keeps links within the same netloc.
    """
    resp = requests.get(base_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    base_netloc = urlparse(base_url).netloc

    links: Set[str] = set()

    for a in soup.select("a[href]"):
        href = a.get("href")
        if not href:
            continue

        url = urljoin(base_url, href)
        parsed = urlparse(url)

        if parsed.netloc != base_netloc:
            continue

        if parsed.scheme not in ("http", "https"):
            continue

        links.add(url)

    return links


def _fetch_page(url: str) -> tuple[str, str, dict]:
    """
    Fetch a page and return:
      (raw_html, extracted_readable_text, response_headers)
    """
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    html = resp.text

    # Readability-based extraction
    doc = Document(html)
    soup = BeautifulSoup(doc.summary(html_partial=True), "html.parser")
    text = "\n".join(
        p.get_text(" ", strip=True)
        for p in soup.find_all("p")
    ).strip()

    return html, text, dict(resp.headers)


# ---------------------------------------------------------------------------
# Core ingest
# ---------------------------------------------------------------------------

def fetch_posts(limit_per_source: int = 25) -> int:
    """
    Scrape HTTP sources and ingest into records.db.

    Behavior:
    - Discovers article links from channel_name (base URL)
    - Uses FULL canonical article URL as source_post_id
    - Extracts published_at using strict heuristics
    - Applies MarianMT translation for non-English sources
    - fetched_at is always authoritative
    """
    _require_records_db()
    sources = _load_sources()

    if not sources:
        logger.warning("No active HTTP sources")
        return 0

    translator = MarianTranslator()
    inserted = 0
    now = datetime.now(UTC)

    with sqlite3.connect(_DB_FILE) as conn:
        for cfg in sources:
            logger.info("Scraping HTTP source: %s", cfg.channel_name)

            try:
                links = list(_discover_links(cfg.channel_name))[:limit_per_source]
            except Exception as e:
                logger.warning("Failed to fetch %s: %s", cfg.channel_name, e)
                continue

            for url in links:
                try:
                    html, raw_text, headers = _fetch_page(url)
                except Exception:
                    continue

                if not raw_text:
                    continue

                # ------------------------------------------------------------
                # Publication date extraction
                # ------------------------------------------------------------
                published_at, confidence = extract_published_at(
                    html=html,
                    url=url,
                    headers=headers,
                )

                if not published_at:
                    published_at = now
                    confidence = None

                # ------------------------------------------------------------
                # Translation
                # ------------------------------------------------------------
                lang = cfg.channel_lang

                if lang != "en":
                    try:
                        text = translator.translate(raw_text, source_lang=lang)
                        lang = "en"
                    except Exception:
                        continue
                else:
                    text = raw_text

                # ------------------------------------------------------------
                # Annotate confidence (optional but recommended)
                # ------------------------------------------------------------
                if confidence:
                    text = f"[PUBLISHED_AT:{confidence}]\n{text}"

                # ------------------------------------------------------------
                # Ingest
                # ------------------------------------------------------------
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO ingest_posts
                    (source, publisher, source_post_id,
                     alias, lang, published_at, fetched_at, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "http",
                        cfg.channel_name,
                        url,                       # RAW canonical URL
                        cfg.alias,
                        lang,
                        _utc_iso(published_at),
                        _utc_iso(now),
                        text,
                    ),
                )

                if cur.rowcount == 1:
                    inserted += 1

        conn.commit()

    return inserted
