# src/sitrepc2/gazetteer/index.py
from __future__ import annotations

from typing import Dict, List, Optional, Iterable
import math

from sitrepc2.util.normalize import normalize_location_key
from sitrepc2.util.encoding import decode_coord_u64

from sitrepc2.gazetteer.typedefs import (
    LocaleEntry,
    RegionEntry,
    GroupEntry,
    DirectionEntry,
)


# ======================================================================
# GazetteerIndex (rewritten)
# ======================================================================

class GazetteerIndex:
    """
    In-memory gazetteer index providing:
      • alias lookups
      • region / group / direction resolution
      • nearest-neighbor spatial search
      • same-name disambiguation logic

    This class receives *already parsed* dataclass lists.
    CSV loading is handled in gazetteer/io.py.
    """

    def __init__(
        self,
        locales: List[LocaleEntry],
        regions: List[RegionEntry],
        groups: List[GroupEntry],
        directions: List[DirectionEntry],
    ):
        self.locales = locales
        self.regions = regions
        self.groups = groups
        self.directions = directions

        # Build lookup maps ---------------------------------------------------
        self._build_locale_maps()
        self._build_region_maps()
        self._build_group_maps()
        self._build_direction_maps()

    # ======================================================================
    # Internal map builders
    # ======================================================================

    def _build_locale_maps(self):
        self._locale_by_alias: Dict[str, List[LocaleEntry]] = {}
        self._locale_by_region: Dict[str, List[LocaleEntry]] = {}
        self._locale_by_cid: Dict[int, LocaleEntry] = {}

        for loc in self.locales:
            # CID lookup
            self._locale_by_cid[loc.cid] = loc

            # region → list
            if loc.region:
                region_key = normalize_location_key(loc.region)
                self._locale_by_region.setdefault(region_key, []).append(loc)

            # aliases & name → list
            for alias in loc.aliases + [loc.name]:
                key = normalize_location_key(alias)
                self._locale_by_alias.setdefault(key, []).append(loc)

    def _build_region_maps(self):
        self._region_by_alias: Dict[str, RegionEntry] = {}

        for reg in self.regions:
            for alias in reg.aliases + [reg.name]:
                key = normalize_location_key(alias)
                self._region_by_alias[key] = reg

    def _build_group_maps(self):
        self._group_by_alias: Dict[str, GroupEntry] = {}

        for g in self.groups:
            for alias in g.aliases + [g.name]:
                key = normalize_location_key(alias)
                self._group_by_alias[key] = g

    def _build_direction_maps(self):
        self._direction_by_alias: Dict[str, DirectionEntry] = {}

        for d in self.directions:
            for alias in d.aliases + [d.name]:
                key = normalize_location_key(alias)
                self._direction_by_alias[key] = d

    # ======================================================================
    # Lookup API
    # ======================================================================

    # ---------------------- Direction --------------------------------------

    def search_direction(self, text: str) -> Optional[DirectionEntry]:
        key = normalize_location_key(text)

        d = self._direction_by_alias.get(key)
        if d:
            return d

        # allow "x direction"
        if key.endswith(" direction"):
            base = key[:-10].strip()
            return self._direction_by_alias.get(base)

        # allow "direction of x"
        if key.startswith("direction of "):
            base = key[len("direction of "):].strip()
            return self._direction_by_alias.get(base)

        return None

    def search_group(self, text: str) -> Optional[GroupEntry]:
        key = normalize_location_key(text)
        return self._group_by_alias.get(key)

    # ---------------------- Locale -----------------------------------------

    def search_locale(self, text: str) -> List[LocaleEntry]:
        key = normalize_location_key(text)
        return list(self._locale_by_alias.get(key, []))

    def get_locale_by_cid(self, cid: int) -> Optional[LocaleEntry]:
        return self._locale_by_cid.get(cid)

    def has_locale(self, text: str) -> bool:
        return bool(self.search_locale(text))

    # ---------------------- Region -----------------------------------------

    def search_region(self, text: str) -> Optional[RegionEntry]:
        key = normalize_location_key(text)
        reg = self._region_by_alias.get(key)
        if reg:
            return reg

        # tolerate suffix stripping
        for suffix in (" oblast", " region"):
            if key.endswith(suffix):
                base = key[:-len(suffix)]
                reg = self._region_by_alias.get(base)
                if reg:
                    return reg

        return None

    def has_region(self, text: str) -> bool:
        return self.search_region(text) is not None

    # ---------------------- Locale+Region combined -----------------------------------------

    def locales_in_region(self, region_text: str) -> List[LocaleEntry]:
        region_key = normalize_location_key(region_text)
        return list(self._locale_by_region.get(region_key, []))

    def search_locale_in_region(self, text: str, region_text: Optional[str]):
        if region_text is None:
            return self.search_locale(text)

        region_key = normalize_location_key(region_text)
        candidates = self.search_locale(text)
        return [
            loc for loc in candidates
            if loc.region and normalize_location_key(loc.region) == region_key
        ]

    # ---------------------- Locale + RU Group -----------------------------------------------

    def search_locale_in_ru_group(self, text: str, ru_group: Optional[str]):
        if ru_group is None:
            return self.search_locale(text)

        ru_group = normalize_location_key(ru_group)
        return [
            loc for loc in self.search_locale(text)
            if loc.ru_group and normalize_location_key(loc.ru_group) == ru_group
        ]

    # ======================================================================
    # Nearest-neighbor functions
    # ======================================================================

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2) -> float:
        R = 6371.0
        lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(a))

    def nearest_locale(self, lat: float, lon: float):
        best = None
        best_dist = float("inf")

        for loc in self.locales:
            d = self._haversine_km(lat, lon, loc.lat, loc.lon)
            if d < best_dist:
                best = loc
                best_dist = d

        return best, best_dist

    def nearest_locale_by_cid(self, cid: int):
        lat, lon = decode_coord_u64(cid)
        return self.nearest_locale(lat, lon)

    def nearest_locales(self, lat: float, lon: float, n: int = 5):
        scored = [
            (self._haversine_km(lat, lon, loc.lat, loc.lon), loc)
            for loc in self.locales
        ]
        scored.sort(key=lambda x: x[0])
        return scored[:n]

    def nearest_locales_within(self, lat: float, lon: float, km: float):
        out = []
        for loc in self.locales:
            d = self._haversine_km(lat, lon, loc.lat, loc.lon)
            if d <= km:
                out.append((d, loc))
        return sorted(out, key=lambda x: x[0])

    # ======================================================================
    # Name-based disambiguation
    # ======================================================================

    def get_locales_by_name(self, name: str) -> List[LocaleEntry]:
        key = normalize_location_key(name)
        return list(self._locale_by_alias.get(key, []))

    def nearest_locale_with_name(self, name: str, lat: float, lon: float):
        candidates = self.get_locales_by_name(name)
        if not candidates:
            return None, None

        best = None
        best_dist = float("inf")
        for loc in candidates:
            d = self._haversine_km(lat, lon, loc.lat, loc.lon)
            if d < best_dist:
                best = loc
                best_dist = d

        return best, best_dist

    def nearest_same_name_from_locale(self, name: str, source_locale: LocaleEntry):
        lat0, lon0 = source_locale.lat, source_locale.lon
        candidates = self.get_locales_by_name(name)

        if not candidates:
            return None, None

        best = None
        best_dist = float("inf")

        for loc in candidates:
            if loc.cid == source_locale.cid:
                continue
            d = self._haversine_km(lat0, lon0, loc.lat, loc.lon)
            if d < best_dist:
                best = loc
                best_dist = d

        if best is None and len(candidates) == 1:
            return candidates[0], 0.0

        return best, best_dist
