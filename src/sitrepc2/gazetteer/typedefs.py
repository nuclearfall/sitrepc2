# src/sitrepc2/gazetteer/typedefs.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List



# ---------------------------------------------------------------------------
# Gazetteer Entry
# ---------------------------------------------------------------------------

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
    cid: int # 64 bit coordinate-based id
    name: str
    aliases: List[str]

    lon: float
    lat: float

    region: Optional[str] = None
    ru_group: Optional[str] = None
    place: Optional[str] = None
    wikidata: Optional[str] = None
    usage: int = 0
    source: str = "base"


@dataclass(frozen=True)
class RegionEntry:
    name: str
    wikidata: str
    iso3166_2: str
    aliases: List[str]
    neighbors: List[str]

@dataclass(frozen=True)
class GroupEntry:
    """Russian Group AO entities."""
    name: str
    group_id: int
    aliases: List[str]
    regions: List[str]
    neighbors: List[str]

@dataclass(frozen=True)
class DirectionEntry:
    name: str
    aliases: List[str] # eg, Kupiansk, Kupyansk ...
    anchor: int # location cid of the anchoring location


