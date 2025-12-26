# src/dbeditc2/models.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class EntrySummary:
    """
    Lightweight, UI-facing summary of an entry displayed
    in the EntryListView.

    This object intentionally contains no database semantics.
    """
    entry_id: Any
    display_name: str
    subtitle: Optional[str] = None
    editable: bool = False


@dataclass(slots=True)
class GazetteerEntityViewModel:
    """
    View model for gazetteer entities (locations, regions,
    groups, directions) as displayed in the details panel.

    Fields are semantic and presentation-oriented.
    """
    title: str
    is_read_only: bool

    # Core attributes (display only unless editable)
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_type: Optional[str] = None
    wikidata_id: Optional[str] = None

    # Related semantic lists
    aliases: list[str] = None
    regions: list[str] = None
    groups: list[str] = None


@dataclass(slots=True)
class LexiconPhraseViewModel:
    """
    View model for lexicon phrases as displayed
    in the phrase constructor panel.
    """
    phrase_text: str
    is_event_phrase: bool
    is_read_only: bool
