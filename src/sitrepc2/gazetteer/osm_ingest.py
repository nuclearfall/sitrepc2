from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence, Set
import re
import sqlite3
import unicodedata

import osmium
from shapely.geometry import Point
from shapely import wkb
from shapely.prepared import prep
from rtree.index import Index as RTreeIndex


# =============================================================================
# Normalization / IDs
# =============================================================================

_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_WS_RE = re.compile(r"\s+", re.UNICODE)


def normalize_alias(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    text = _WORD_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def encode_coord_u64(lat: float, lon: float) -> int:
    lat = round(lat, 6)
    lon = round(lon, 6)
    lat_u32 = int((lat + 90.0) * 1_000_000)
    lon_u32 = int((lon + 180.0) * 1_000_000)
    return (lat_u32 << 32) | lon_u32


# =============================================================================
# Name extraction
# =============================================================================

_ALLOWED_NAME_BASES: Set[str] = {
    "name",
    "official_name",
    "loc_name",
    "short_name",
    "name_old",
    "name_alt",
}

_CANONICAL_PREF_ORDER: Sequence[str] = (
    "name",
    "official_name",
    "short_name",
    "loc_name",
    "name_alt",
    "name_old",
)

_ALLOWED_PLACES: Set[str] = {
    "city",
    "town",
    "village",
    "hamlet",
    "suburb",
    "locality",
    "isolated_dwelling",
    "farm",
    "urban_type_settlement",
    "settlement",
}


def iter_lang_names(tags: osmium.osm.TagList, lang: str):
    suffix = f":{lang}"
    for k, v in tags:
        if k.endswith(suffix):
            base = k[:-len(suffix)]
            if base in _ALLOWED_NAME_BASES and v:
                yield base, v


def choose_canonical_name(lang_names):
    if not lang_names:
        return None
    by_base = {}
    for base, val in lang_names:
        by_base.setdefault(base, []).append(val)
    for base in _CANONICAL_PREF_ORDER:
        if base in by_base:
            return by_base[base][0]
    return lang_names[0][1]


# =============================================================================
# Result
# =============================================================================

@dataclass(frozen=True, slots=True)
class OSMIngestResult:
    osm_pbf_path: Path
    gazetteer_db_path: Path
    user_lang: str
    admin_levels: tuple[int, ...]

    location_count: int
    location_alias_count: int
    admin_area_count: int
    admin_area_alias_count: int
    location_admin_area_count: int

    started_at: datetime
    completed_at: datetime


# =============================================================================
# Handlers
# =============================================================================

class PlaceNodeHandler(osmium.SimpleHandler):
    def __init__(self, user_lang: str):
        super().__init__()
        self.user_lang = user_lang
        self.locations = []
        self.location_aliases = []
        self._seen_loc = set()
        self._seen_alias = set()

    def node(self, n: osmium.osm.Node):
        if not n.location.valid():
            return
        place = n.tags.get("place")
        if place not in _ALLOWED_PLACES:
            return

        names = list(iter_lang_names(n.tags, self.user_lang))
        canonical = choose_canonical_name(names)
        if not canonical:
            return

        lat, lon = n.location.lat, n.location.lon
        loc_id = encode_coord_u64(lat, lon)

        if loc_id not in self._seen_loc:
            self.locations.append(
                (loc_id, lat, lon, canonical, n.tags.get("wikidata"))
            )
            self._seen_loc.add(loc_id)

        for _, name in names:
            norm = normalize_alias(name)
            pk = (loc_id, norm)
            if norm and pk not in self._seen_alias:
                self.location_aliases.append((loc_id, name, norm))
                self._seen_alias.add(pk)


class AdminAreaAreaHandler(osmium.SimpleHandler):
    """
    Extract administrative areas using osmium's area assembly.
    Works with python-osmium (no AreaHandler class exists).
    """

    def __init__(self, user_lang: str, admin_levels: set[int]):
        super().__init__()
        self.user_lang = user_lang
        self.admin_levels = admin_levels

        self.admin_areas: list[tuple[int, int, str | None, str | None, bytes]] = []
        self.admin_area_aliases: list[tuple[int, str, str, str]] = []

        self._wkb_factory = osmium.geom.WKBFactory()
        self._seen_admin_id: set[int] = set()
        self._seen_alias_pk: set[tuple[int, str]] = set()

    def area(self, a: osmium.osm.Area) -> None:
        tags = a.tags

        if tags.get("boundary") != "administrative":
            return

        try:
            level = int(tags.get("admin_level"))
        except (TypeError, ValueError):
            return

        if level not in self.admin_levels:
            return

        admin_id = int(a.id)
        if admin_id in self._seen_admin_id:
            return

        try:
            wkb_bytes = self._wkb_factory.create_multipolygon(a)
        except Exception:
            return

        # Names
        lang_names = list(iter_lang_names(tags, self.user_lang))
        canonical = choose_canonical_name(lang_names)
        wikidata = tags.get("wikidata")

        self.admin_areas.append(
            (admin_id, level, canonical, wikidata, wkb_bytes)
        )
        self._seen_admin_id.add(admin_id)

        for _, name_val in lang_names:
            norm = normalize_alias(name_val)
            pk = (admin_id, norm)
            if not norm or pk in self._seen_alias_pk:
                continue
            self.admin_area_aliases.append(
                (admin_id, name_val, norm, "OSM")
            )
            self._seen_alias_pk.add(pk)


# =============================================================================
# SQLite schema
# =============================================================================

_GAZETTEER_DDL = """<UNCHANGED — use your existing DDL verbatim>"""


# =============================================================================
# Public API
# =============================================================================

def ingest_osm(
    *,
    osm_pbf_path: Path,
    gazetteer_db_path: Path = Path("gazetteer.db"),
    user_lang: str = "en",
    admin_levels: set[int] = {2, 4, 6},
    overwrite: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> OSMIngestResult:

    started_at = datetime.utcnow()
    osm_pbf_path = osm_pbf_path.expanduser().resolve()
    gazetteer_db_path = gazetteer_db_path.expanduser().resolve()

    if gazetteer_db_path.exists():
        if not overwrite:
            raise FileExistsError(gazetteer_db_path)
        gazetteer_db_path.unlink()

    def log(msg):
        if progress_cb:
            progress_cb(msg)

    log("OSM ingest: places")
    place_handler = PlaceNodeHandler(user_lang)
    place_handler.apply_file(str(osm_pbf_path), locations=False)

    log("OSM ingest: admin areas (AreaHandler)")
    admin_handler = AdminAreaAreaHandler(user_lang, admin_levels)
    # Build location index (required for area assembly)
    loc_index = osmium.index.create_map("flex_mem")
    loc_cache = osmium.geom.NodeLocationsForWays(loc_index)

    # Area manager assembles multipolygons
    area_manager = osmium.area.AreaManager()

    # Apply OSM file through location cache + area manager
    admin_handler.apply(
        str(osm_pbf_path),
        loc_cache,
        area_manager,
    )
    area_manager.flush()

    log("OSM ingest: containment")
    rtree = RTreeIndex()
    prepared = {}

    for admin_id, _, _, _, geom_wkb in admin_handler.admin_areas:
        try:
            geom = wkb.loads(geom_wkb)
            prepared[admin_id] = prep(geom)
            rtree.insert(admin_id, geom.bounds)
        except Exception:
            continue

    location_admin = []
    for loc_id, lat, lon, *_ in place_handler.locations:
        pt = Point(lon, lat)
        for admin_id in rtree.intersection((lon, lat, lon, lat)):
            if prepared[admin_id].contains(pt):
                location_admin.append((loc_id, admin_id))

    log("OSM ingest: writing DB")
    con = sqlite3.connect(gazetteer_db_path)
    try:
        cur = con.cursor()
        cur.executescript(_GAZETTEER_DDL)

        cur.executemany(
            "INSERT INTO locations VALUES (?, ?, ?, ?, ?)",
            place_handler.locations,
        )
        cur.executemany(
            "INSERT OR IGNORE INTO location_aliases VALUES (?, ?, ?)",
            place_handler.location_aliases,
        )
        cur.executemany(
            "INSERT INTO admin_areas VALUES (?, ?, ?, ?, ?)",
            admin_handler.admin_areas,
        )
        cur.executemany(
            "INSERT OR IGNORE INTO admin_area_aliases VALUES (?, ?, ?, ?)",
            admin_handler.admin_area_aliases,
        )
        cur.executemany(
            "INSERT OR IGNORE INTO location_admin_areas VALUES (?, ?)",
            location_admin,
        )
        con.commit()
    finally:
        con.close()

    completed_at = datetime.utcnow()

    return OSMIngestResult(
        osm_pbf_path,
        gazetteer_db_path,
        user_lang,
        tuple(sorted(admin_levels)),
        len(place_handler.locations),
        len(place_handler.location_aliases),
        len(admin_handler.admin_areas),
        len(admin_handler.admin_area_aliases),
        len(location_admin),
        started_at,
        completed_at,
    )
