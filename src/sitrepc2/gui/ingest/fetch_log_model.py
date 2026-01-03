from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True, slots=True)
class FetchLogEntry:
    timestamp: str
    source_name: str
    source_kind: str
    start_date: str
    end_date: Optional[str]
    force: bool
    fetched_count: int
    error: Optional[str] = None


class FetchLogModel:
    """
    Simple in-memory fetch log.
    GUI-owned, not persisted.
    """

    def __init__(self) -> None:
        self._entries: List[FetchLogEntry] = []

    def add(self, entry: FetchLogEntry) -> None:
        self._entries.insert(0, entry)

    def entries(self) -> List[FetchLogEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()
