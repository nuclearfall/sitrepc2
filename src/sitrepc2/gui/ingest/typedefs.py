from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class IngestState(str, Enum):
    INGESTED = "INGESTED"
    EXTRACTED = "EXTRACTED"
    DOM_INITIAL = "DOM_INITIAL"
    DOM_PROCESSED = "DOM_PROCESSED"
    COMMITTED = "COMMITTED"


@dataclass(slots=True)
class SourceEntry:
    source_name: str
    alias: str
    source_kind: str
    lang: str
    active: bool


@dataclass(slots=True)
class IngestPostEntry:
    post_id: int
    source: str
    publisher: str
    alias: str
    lang: str
    published_at: datetime
    text: str
    state: IngestState
