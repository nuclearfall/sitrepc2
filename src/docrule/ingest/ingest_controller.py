from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Set, Dict

from sitrepc2.gui.ingest.typedefs import (
    SourceEntry,
    IngestPostEntry,
    IngestState,
)

from sitrepc2.config.paths import sources_path, records_path
from sitrepc2.ingest import (
    http,
    telegram,
    twitter,
    facebook,
)

logger = logging.getLogger(__name__)

_FETCH_DISPATCH: Dict[str, Callable[..., int]] = {
    "HTTP": http.fetch_posts,
    "TELEGRAM": telegram.fetch_posts,
    "TWITTER": twitter.fetch_posts,
    "FACEBOOK": facebook.fetch_posts,
}


# ============================================================
# INGEST CONTROLLER
# ============================================================

class IngestController:
    """
    Orchestrates ingest workspace state.

    Responsibilities:
    - load sources
    - load posts
    - apply filters
    - track inclusion
    - trigger fetch / extract
    - expose extraction state
    - signal DOM review launch
    """

    def __init__(
        self,
        *,
        load_sources_fn: Callable[[], List[SourceEntry]],
        load_posts_fn: Callable[[], List[IngestPostEntry]],
        fetch_fn: Optional[Callable[[Iterable[SourceEntry], dict], None]] = None,
        extract_fn: Optional[Callable[[Iterable[int]], None]] = None,
        on_state_changed: Optional[Callable[[], None]] = None,
        on_open_dom: Optional[Callable[[int], None]] = None,
    ) -> None:
        self._load_sources_fn = load_sources_fn
        self._load_posts_fn = load_posts_fn
        self._fetch_fn = fetch_fn
        self._extract_fn = extract_fn
        self._on_state_changed = on_state_changed
        self._on_open_dom = on_open_dom

        # -----------------------------
        # State
        # -----------------------------

        self.sources: List[SourceEntry] = []
        self.posts: List[IngestPostEntry] = []

        self.active_source_ids: Set[str] = set()
        self.included_post_ids: Set[int] = set()

        self.start_date: Optional[date] = None
        self.end_date: Optional[date] = None
        self.whitelist: Set[str] = set()
        self.blacklist: Set[str] = set()

        # Derived
        self._extracted_ids: Set[int] = set()

        self._on_lss_progress: Optional[Callable[[LssProgress], None]] = None


    # ========================================================
    # Loading
    # ========================================================

    def load_sources(self) -> None:
        self.sources = self._load_sources_fn()
        self.active_source_ids = {
            s.source_name for s in self.sources if s.active
        }
        self._emit_change()

    def load_posts(self) -> None:
        self.posts = self._load_posts_fn()

        # Default: include all newly ingested posts
        for p in self.posts:
            if p.state == IngestState.INGESTED:
                self.included_post_ids.add(p.post_id)

        self._refresh_extraction_state()
        self._emit_change()

    # ========================================================
    # Extraction state
    # ========================================================

    def _refresh_extraction_state(self) -> None:
        """
        Cache which ingest_post_ids have completed LSS extraction.
        """
        db_path = records_path()
        if not db_path.exists():
            self._extracted_ids = set()
            return

        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT ingest_post_id FROM lss_runs"
            ).fetchall()

        self._extracted_ids = {row[0] for row in rows}

    def extracted_post_ids(self) -> Set[int]:
        return set(self._extracted_ids)

    def is_extracted(self, post_id: int) -> bool:
        return post_id in self._extracted_ids

    # ========================================================
    # Filters
    # ========================================================

    def set_date_range(
        self,
        start: Optional[date],
        end: Optional[date],
    ) -> None:
        self.start_date = start
        self.end_date = end
        self._emit_change()

    def set_whitelist(self, keywords: Iterable[str]) -> None:
        self.whitelist = {k.lower() for k in keywords if k.strip()}
        self._emit_change()

    def set_blacklist(self, keywords: Iterable[str]) -> None:
        self.blacklist = {k.lower() for k in keywords if k.strip()}
        self._emit_change()

    # ========================================================
    # Selection
    # ========================================================

    def toggle_source_active(self, source_name: str, active: bool) -> None:
        if active:
            self.active_source_ids.add(source_name)
        else:
            self.active_source_ids.discard(source_name)
        self._emit_change()

    def toggle_post_included(self, post_id: int, included: bool) -> None:
        if included:
            self.included_post_ids.add(post_id)
        else:
            self.included_post_ids.discard(post_id)
        self._emit_change()

    # ========================================================
    # Derived views
    # ========================================================

    def filtered_sources(self) -> List[SourceEntry]:
        return self.sources

    def filtered_posts(self) -> List[IngestPostEntry]:
        """
        Apply date + keyword filters.
        Inclusion checkbox is NOT a filter.
        """
        result: List[IngestPostEntry] = []

        for p in self.posts:
            if self.start_date and p.published_at.date() < self.start_date:
                continue
            if self.end_date and p.published_at.date() > self.end_date:
                continue

            text = p.text.lower()

            if self.whitelist and not any(k in text for k in self.whitelist):
                continue
            if self.blacklist and any(k in text for k in self.blacklist):
                continue

            result.append(p)

        return result

    def set_lss_progress_handler(
        self,
        handler: Callable[[LssProgress], None],
    ) -> None:
        self._on_lss_progress = handler


    # ========================================================
    # Sources persistence
    # ========================================================

    def save_sources(self) -> None:
        """
        Persist current sources to sources.jsonl.
        """
        path: Path = sources_path()
        lines: List[str] = []

        for src in self.sources:
            record = {
                "source_name": src.source_name,
                "alias": src.alias,
                "source_lang": src.lang,
                "active": bool(src.active),
                "source_kind": src.source_kind,
            }
            lines.append(json.dumps(record, ensure_ascii=False))

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ========================================================
    # Actions
    # ========================================================

    def fetch(self) -> None:
        """
        Fetch posts for all active sources,
        using the currently selected date range.
        """
        if not self.start_date or not self.end_date:
            logger.warning("Fetch aborted: date range not set")
            return

        total_inserted = 0

        active_kinds = {
            src.source_kind
            for src in self.sources
            if src.active
        }

        # Active source names (explicit filter)
        active_source_names = {
            src.source_name
            for src in self.sources
            if src.active
        }

        start = self.start_date.isoformat()
        end = self.end_date.isoformat()

        for kind in sorted(active_kinds):
            fetch_fn = _FETCH_DISPATCH.get(kind)
            if not fetch_fn:
                logger.warning("No fetcher for source_kind=%s", kind)
                continue

            logger.info(
                "Fetching posts for source_kind=%s [%s → %s]",
                kind,
                start,
                end,
            )

            try:
                inserted = fetch_fn(
                    start_date=start,
                    end_date=end,
                    aliases=None,
                    source_name=list(active_source_names),
                )
                total_inserted += inserted
            except Exception:
                logger.exception("Fetch failed for source_kind=%s", kind)

        logger.info("Fetch complete: %d new posts", total_inserted)
        self.load_posts()


    def extract_selected(self) -> None:
        if not self._extract_fn:
            return

        eligible = [
            p.post_id for p in self.posts
            if p.post_id in self.included_post_ids
            and p.state == IngestState.INGESTED
        ]

        if not eligible:
            return

        total = len(eligible)
        completed = 0
        failed = 0

        def progress_cb(post_id: int, success: bool) -> None:
            nonlocal completed, failed
            completed += 1
            if not success:
                failed += 1

            if self._on_lss_progress:
                self._on_lss_progress(
                    LssProgress(
                        total=total,
                        completed=completed,
                        failed=failed,
                        current_post_id=post_id,
                    )
                )

        self._extract_fn(eligible, progress_cb=progress_cb)


    # ========================================================
    # DOM handoff
    # ========================================================

    def open_dom_review(self, ingest_post_id: int) -> None:
        """
        Signal that DOM review should be opened for this post.
        """
        if self._on_open_dom:
            self._on_open_dom(ingest_post_id)

    # ========================================================
    # Utilities
    # ========================================================

    def _emit_change(self) -> None:
        if self._on_state_changed:
            self._on_state_changed()
