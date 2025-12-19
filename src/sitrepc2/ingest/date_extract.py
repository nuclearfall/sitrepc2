from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional, Tuple

from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

UTC = timezone.utc

# ---------------------------------------------------------------------------
# Regex for YYYY/MM/DD or YYYY-MM-DD in URLs
# ---------------------------------------------------------------------------

_URL_DATE_RE = re.compile(
    r"(20\d{2})[/-](\d{2})[/-](\d{2})"
)

# ---------------------------------------------------------------------------
# Core extractor
# ---------------------------------------------------------------------------

def extract_published_at(
    *,
    html: Optional[str] = None,
    url: Optional[str] = None,
    headers: Optional[dict] = None,
) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Attempt to extract a publication datetime from available signals.

    Returns
    -------
    (published_at, confidence)

    confidence ∈ {"meta", "jsonld", "url", "header", None}
    """

    # ------------------------------------------------------------
    # Tier 1a: HTML meta tags
    # ------------------------------------------------------------
    if html:
        soup = BeautifulSoup(html, "html.parser")

        meta_props = [
            "article:published_time",
            "og:published_time",
            "pubdate",
            "publishdate",
            "timestamp",
            "date",
        ]

        for prop in meta_props:
            tag = soup.find("meta", {"property": prop}) or soup.find("meta", {"name": prop})
            if tag and tag.get("content"):
                dt = _parse_iso_datetime(tag["content"])
                if dt:
                    return dt, "meta"

        # --------------------------------------------------------
        # Tier 1b: JSON-LD
        # --------------------------------------------------------
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string or "")
            except Exception:
                continue

            if isinstance(data, dict):
                date_str = data.get("datePublished") or data.get("dateCreated")
                dt = _parse_iso_datetime(date_str)
                if dt:
                    return dt, "jsonld"

    # ------------------------------------------------------------
    # Tier 2: URL path inference
    # ------------------------------------------------------------
    if url:
        m = _URL_DATE_RE.search(url)
        if m:
            try:
                y, mth, d = map(int, m.groups())
                return datetime(y, mth, d, tzinfo=UTC), "url"
            except Exception:
                pass

    # ------------------------------------------------------------
    # Tier 3: HTTP headers
    # ------------------------------------------------------------
    if headers:
        lm = headers.get("Last-Modified")
        if lm:
            try:
                dt = parsedate_to_datetime(lm)
                if dt:
                    return dt.astimezone(UTC), "header"
            except Exception:
                pass

    return None, None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_iso_datetime(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None
