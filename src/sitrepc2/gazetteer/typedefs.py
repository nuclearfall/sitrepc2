# src/sitrepc2/nlp/typedefs.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List

class DirectionEntry:
    """Placeholder for direction/axis representation."""
    label: str = "UNKNOWN_DIRECTION"

    def __init__(self, label: str = "UNKNOWN_DIRECTION"):
        self.label = label


class GroupEntry:
    """Placeholder for Russian/Ukrainian group AO entities."""
    name: str = "UNKNOWN_GROUP"

    def __init__(self, name: str = "UNKNOWN_GROUP"):
        self.name = name

# ---------------------------------------------------------------------------
# Basic Coordinate Type
# ---------------------------------------------------------------------------

@dataclass
class Coordinates:
    """
    Represents geographic coordinates.
    Lat/lon order is enforced to avoid confusion.
    """
    lat: float
    lon: float


# ---------------------------------------------------------------------------
# Gazetteer Entry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LocaleEntry:
    """
    Canonical representation of a mappable place.
    May be:
      - from locale_lookup.csv
      - patch entry
      - user-defined coordinate point
    """
    id: str
    name: str
    aliases: List[str]
    coordinates: Coordinates

    region: Optional[str] = None
    group: Optional[str] = None
    place: Optional[str] = None
    wikidata: Optional[str] = None
    usage: int = 0
    source: str = "base"      # "base" | "patch" | "manual"
