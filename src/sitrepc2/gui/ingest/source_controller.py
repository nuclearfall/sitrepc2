from __future__ import annotations

import json
import importlib
from dataclasses import dataclass, replace
from datetime import datetime
from typing import List, Optional, Dict, Any

from sitrepc2.config.paths import sources_path


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_name: str          # canonical identifier
    alias: str                # human-facing label
    source_kind: str          # TELEGRAM / FACEBOOK / TWITTER / HTTP
    source_lang: str          # expected language
    active: bool = True       # enabled / disabled


@dataclass(frozen=True, slots=True)
class FetchResult:
    timestamp: str            # ISO-8601 UTC
    source_name: str
    source_kind: str
    start_date: str
    end_date: Optional[str]
    force: bool
    fetched_count: int
    error: Optional[str] = None


# ============================================================================
# SOURCE CONTROLLER
# ============================================================================

class SourceController:
    """
    Controller responsible for:
    - Source registry CRUD (JSONL)
    - Dispatching fetch operations to ingest adapters
    - Returning structured fetch results for GUI logging

    This controller:
    - NEVER touches SQLite
    - NEVER interprets ingest_posts
    - NEVER imports GUI code
    """

    # ------------------------------------------------------------------
    # Source registry
    # ------------------------------------------------------------------

    def load_sources(self) -> List[SourceRecord]:
        path = sources_path()
        if not path.exists():
            return []

        records: List[SourceRecord] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                records.append(
                    SourceRecord(
                        source_name=data["source_name"],
                        alias=data["alias"],
                        source_kind=data["source_kind"],
                        source_lang=data["source_lang"],
                        active=bool(data.get("active", True)),
                    )
                )
        return records

    # ------------------------------------------------------------------

    def save_sources(self, sources: List[SourceRecord]) -> None:
        """
        Persist the entire source registry atomically.
        """
        path = sources_path()
        tmp_path = path.with_suffix(".tmp")

        with tmp_path.open("w", encoding="utf-8") as fh:
            for src in sources:
                fh.write(
                    json.dumps(
                        {
                            "source_name": src.source_name,
                            "alias": src.alias,
                            "source_kind": src.source_kind,
                            "source_lang": src.source_lang,
                            "active": src.active,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        tmp_path.replace(path)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def add_source(self, record: SourceRecord) -> None:
        sources = self.load_sources()
        if any(s.source_name == record.source_name for s in sources):
            raise ValueError(f"Source '{record.source_name}' already exists")
        sources.append(record)
        self.save_sources(sources)

    # ------------------------------------------------------------------

    def update_source(self, source_name: str, **changes: Any) -> None:
        """
        Update fields on an existing source (does NOT change source_name).
        """
        sources = self.load_sources()
        updated: List[SourceRecord] = []
        found = False

        for src in sources:
            if src.source_name == source_name:
                updated.append(replace(src, **changes))
                found = True
            else:
                updated.append(src)

        if not found:
            raise KeyError(f"Source '{source_name}' not found")

        self.save_sources(updated)

    # ------------------------------------------------------------------

    def replace_source(self, old_source_name: str, new_record: SourceRecord) -> None:
        """
        Replace an existing source record entirely, allowing source_name changes.

        Rules:
        - old_source_name must exist
        - if new_record.source_name differs, it must be unique
        """
        sources = self.load_sources()

        if not any(s.source_name == old_source_name for s in sources):
            raise KeyError(f"Source '{old_source_name}' not found")

        if new_record.source_name != old_source_name:
            if any(s.source_name == new_record.source_name for s in sources):
                raise ValueError(
                    f"Source '{new_record.source_name}' already exists"
                )

        replaced: List[SourceRecord] = []
        for src in sources:
            if src.source_name == old_source_name:
                replaced.append(new_record)
            else:
                replaced.append(src)

        self.save_sources(replaced)

    # ------------------------------------------------------------------

    def set_active(self, source_names: List[str], active: bool) -> None:
        sources = self.load_sources()
        updated: List[SourceRecord] = []

        names = set(source_names)
        for src in sources:
            if src.source_name in names:
                updated.append(replace(src, active=active))
            else:
                updated.append(src)

        self.save_sources(updated)

    # ------------------------------------------------------------------

    def delete_source_hard(self, source_name: str) -> None:
        """
        Hard delete: remove the entry entirely from JSONL.
        """
        sources = self.load_sources()
        kept = [s for s in sources if s.source_name != source_name]

        if len(kept) == len(sources):
            raise KeyError(f"Source '{source_name}' not found")

        self.save_sources(kept)

    # ============================================================================
    # FETCHING
    # ============================================================================

    def fetch_sources(
        self,
        source_names: List[str],
        start_date: str,
        end_date: Optional[str] = None,
        *,
        force: bool = False,
    ) -> List[FetchResult]:
        """
        Fetch posts for the given sources.

        Dispatch is grouped by source_kind.
        Only ACTIVE sources are fetched.
        """
        sources = [
            s for s in self.load_sources()
            if s.source_name in set(source_names) and s.active
        ]

        by_kind: Dict[str, List[SourceRecord]] = {}
        for src in sources:
            by_kind.setdefault(src.source_kind, []).append(src)

        results: List[FetchResult] = []

        for kind, group in by_kind.items():
            module = self._load_ingest_module(kind)
            names = [s.source_name for s in group]

            try:
                count = module.fetch_posts(
                    start_date=start_date,
                    end_date=end_date,
                    source_name=names,
                    force=force,
                )

                for src in group:
                    results.append(
                        FetchResult(
                            timestamp=self._now(),
                            source_name=src.source_name,
                            source_kind=src.source_kind,
                            start_date=start_date,
                            end_date=end_date,
                            force=force,
                            fetched_count=count,
                        )
                    )

            except Exception as exc:
                for src in group:
                    results.append(
                        FetchResult(
                            timestamp=self._now(),
                            source_name=src.source_name,
                            source_kind=src.source_kind,
                            start_date=start_date,
                            end_date=end_date,
                            force=force,
                            fetched_count=0,
                            error=str(exc),
                        )
                    )

        return results

    # ============================================================================
    # INTERNALS
    # ============================================================================

    def _load_ingest_module(self, source_kind: str):
        mapping = {
            "FACEBOOK": "sitrepc2.ingest.facebook",
            "TELEGRAM": "sitrepc2.ingest.telegram",
            "TWITTER": "sitrepc2.ingest.twitter",
            "HTTP": "sitrepc2.ingest.http",
        }

        if source_kind not in mapping:
            raise ValueError(f"Unknown source_kind '{source_kind}'")

        return importlib.import_module(mapping[source_kind])

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"
