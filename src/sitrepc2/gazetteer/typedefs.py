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

from dataclasses import dataclass
from typing import Optional, List

@dataclass(frozen=True)
class LocaleEntry:
    """
    Canonical representation of a mappable place in the sitrepc2 gazetteer.
    Derived directly from locale_lookup.csv (base) or patch CSVs.

    Fields:
      - name: primary display name
      - aliases: alternate names, spellings, exonyms (list[str])
      - lon, lat: normalized WGS84 coordinates
      - cid: 64-bit packed coordinate identity (encode_coord_u64)
      - region: oblast (optional)
      - ru_group: Russian Military District / Operational Group (optional)
      - place: settlement type ("city", "village", etc.)
      - wikidata: external ID (optional)
      - usage: integer usage counter
      - source: "base" | "patch" | "manual"
    """

    name: str
    aliases: List[str]

    lon: float
    lat: float
    cid: int

    region: Optional[str] = None
    ru_group: Optional[str] = None
    place: Optional[str] = None
    wikidata: Optional[str] = None
    usage: int = 0
    source: str = "base"



