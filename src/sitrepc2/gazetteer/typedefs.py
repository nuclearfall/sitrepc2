# src/sitrepc2/gazetteer/typedefs.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List


# ---------------------------------------------------------------------------
# Gazetteer Entry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LocaleEntry:
    """
    Canonical representation of a mappable place in the sitrepc2 gazetteer.
    Derived from the authoritative SQLite workspace database.

    Fields aligned with the canonical database schema:
      - cid: primary key (TEXT in DB), canonical string form of a 64-bit
             coordinate-based ID (encode_coord_u64).
      - name: primary display name
      - aliases: alternate names, spellings, exonyms (list[str])
      - lon, lat: normalized WGS84 coordinates
      - region_id: FK to RegionEntry.osm_id (may be None)
      - group_id: FK to GroupEntry.group_id (may be None)
      - place: settlement type ("city", "village", etc.)
      - wikidata: external ID (optional)
      - usage: integer usage counter
      - source: "base" | "patch" | "manual"
    """

    # Keys + core identity
    cid: str  # string form of the 64-bit coordinate-based id
    name: str
    aliases: List[str]

    # Geometry
    lon: float
    lat: float

    # Relational keys
    region_id: Optional[int] = None  # regions.osm_id
    group_id: Optional[int] = None   # groups.group_id

    # Metadata
    place: Optional[str] = None
    wikidata: Optional[str] = None
    usage: int = 0
    source: str = "base"


@dataclass(frozen=True)
class RegionEntry:
    """
    Canonical region record, aligned with the authoritative SQLite 
    workspace database:

        osm_id,wikidata,iso3166_2,name,aliases,neighbors

    - osm_id: primary key (admin_level=4 OSM relation ID)
    - neighbors: list of neighboring region osm_ids
    """
    osm_id: int
    name: str

    wikidata: Optional[str] = None
    iso3166_2: Optional[str] = None

    aliases: List[str] = field(default_factory=list)
    neighbors: List[int] = field(default_factory=list)  # neighbor osm_ids


@dataclass(frozen=True)
class GroupEntry:
    """
    Russian Group of Forces entity, aligned with the authoritative 
    SQLite workspace database

        name,group_id,aliases,region_ids,neighbor_ids

    - group_id: primary key
    - region_ids: list of region osm_ids covered by this group
    - neighbor_ids: list of other group_ids considered adjacent/related
    """
    group_id: int
    name: str

    aliases: List[str] = field(default_factory=list)

    # FK-style references by ID
    region_ids: List[int] = field(default_factory=list)    # regions.osm_id
    neighbor_ids: List[int] = field(default_factory=list)  # other groups.group_id


@dataclass(frozen=True)
class DirectionEntry:
    """
    Direction entity, aligned with the authoritative SQLite workspace 
    database:

        dir_id (PK, in DB only)
        name,anchor_cid

    - dir_id: primary key in the DB (may be None for in-memory-only entries)
    - name: direction name ("avdiivka", "bakhmut", etc.)
    - anchor_cid: FK to LocaleEntry.cid (the anchor locale)
    - anchor: optional resolved LocaleEntry for convenience
    - aliases: optional list of variant names / spellings
    """
    dir_id: Optional[int]
    name: str

    anchor_cid: str                  # locales.cid
    anchor: Optional[LocaleEntry] = None  # resolved anchor, if available

    aliases: List[str] = field(default_factory=list)
