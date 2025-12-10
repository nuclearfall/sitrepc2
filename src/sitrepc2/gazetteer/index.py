from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import List, Sequence, Optional

from sitrepc2.config.paths import resolve_gazetteer_paths
from sitrepc2.util.normalize import normalize_location_key
from sitrepc2.util.serialization import serialize, deserialize
from sitrepc2.util.encoding import decode_coord_u64

from sitrepc2.gazetteer.typedefs import (
    LocaleEntry,
    RegionEntry,
    GroupEntry,
    DirectionEntry,
)   

# ---------------------------------------------------------------------------
# Alias packing / unpacking
# ---------------------------------------------------------------------------

def _unpack_aliases(aliases_str: str | None) -> list[str]:
    """
    Convert a semicolon-separated alias string into a list[str].
    """
    if aliases_str is None:
        return []
    if not isinstance(aliases_str, str):
        raise TypeError(f"Expected str or None, got {type(aliases_str)}")

    return [a.strip() for a in aliases_str.split(";") if a.strip()]


def _pack_aliases(aliases_ls: list[str] | None) -> str:
    """
    Convert list[str] back into the canonical semicolon-separated CSV string.
    """
    if aliases_ls is None:
        return ""
    if not isinstance(aliases_ls, list):
        raise TypeError(f"Expected list[str] or None, got {type(aliases_ls)}")

    return ";".join(a.strip() for a in aliases_ls if a.strip())


def _pack_obj_aliases(objs: list[object]) -> list[object]:
    """
    Given a list of dataclass objects, return modified dicts from serialize(),
    with aliases packed into CSV format.
    """
    out = []
    for obj in objs:
        d = serialize(obj)
        aliases = d.get("aliases", None)
        d["aliases"] = _pack_aliases(aliases)
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Gazetteer Index
# ---------------------------------------------------------------------------

class GazetteerIndex:
    """
    In-memory index for locales, regions, and directions.
    """

    def __init__(
        self,
        locales: List[LocaleEntry],
        regions: List[RegionEntry],
        directions: List[DirectionEntry],
    ) -> None:

        self.locales = locales
        self.regions = regions
        self.directions = directions

        # alias_key → List[LocaleEntry]
        self._locale_by_alias: dict[str, List[LocaleEntry]] = {}

        # alias_key → RegionEntry
        self._region_by_alias: dict[str, RegionEntry] = {}

        # alias_key → DirectionEntry
        self._direction_by_alias: dict[str, DirectionEntry] = {}  # NEW

        # region_name → List[LocaleEntry]
        self._locale_by_region: dict[str, List[LocaleEntry]] = {}

        # cid → LocaleEntry
        self._locale_by_cid: dict[int, LocaleEntry] = {
            loc.cid: loc for loc in locales
        }

        self._build_indexes()

    # ------------------------------------------------------------------ #
    # Index construction
    # ------------------------------------------------------------------ #

    def _build_indexes(self) -> None:
        # --- locales
        for loc in self.locales:
            for alias in loc.aliases:
                key = normalize_location_key(alias)
                self._locale_by_alias.setdefault(key, []).append(loc)

            if loc.region:
                region_key = normalize_location_key(loc.region)
                self._locale_by_region.setdefault(region_key, []).append(loc)

        # --- regions: enforce unique alias mapping
        for reg in self.regions:
            for alias in reg.aliases:
                key = normalize_location_key(alias)
                if key in self._region_by_alias:
                    raise ValueError(
                        f"Duplicate region alias '{alias}' mapping to multiple regions: "
                        f"{self._region_by_alias[key].name!r} and {reg.name!r}"
                    )
                self._region_by_alias[key] = reg

        # --- directions: enforce unique alias mapping (NEW)
        for d in self.directions:
            for alias in d.aliases:
                key = normalize_location_key(alias)
                if key in self._direction_by_alias:
                    raise ValueError(
                        f"Duplicate direction alias '{alias}' mapping multiple directions: "
                        f"{self._direction_by_alias[key].name!r} and {d.name!r}"
                    )
                self._direction_by_alias[key] = d

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    @classmethod
    def load_canonical(
        cls,
        root: Path | None = None,
        encoding: str = "utf-8",
    ) -> "GazetteerIndex":
        """
        Expected file order from resolve_gazetteer_paths:
        1. locales
        2. regions
        3. directions
        """
        out: list[list[object]] = []

        for path in resolve_gazetteer_paths(root):
            entries: list[object] = []
            with path.open("r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row["aliases"] = _unpack_aliases(row.get("aliases"))

                    # numeric conversions
                    if row.get("lon"): row["lon"] = float(row["lon"])
                    if row.get("lat"): row["lat"] = float(row["lat"])
                    if row.get("cid"): row["cid"] = int(row["cid"])
                    if row.get("anchor"): row["anchor"] = int(row["anchor"])

                    # dynamic dataclass detection
                    if "anchor" in row:
                        entries.append(deserialize(row, DirectionEntry))
                    elif "neighbors" in row or "wikidata" in row:
                        entries.append(deserialize(row, RegionEntry))
                    else:
                        entries.append(deserialize(row, LocaleEntry))

            out.append(entries)

        locales, regions, directions = out[:3]
        return cls(locales=locales, regions=regions, directions=directions)


    @classmethod
    def load_patch(
        cls,
        file_path: Path | str,
        root: Path | None = None,
        encoding: str = "utf-8",
    ) -> List[LocaleEntry]:
        """Load a patch CSV and return a list of LocaleEntry objects."""
        if root is None:
            raise ValueError("root must not be None")

        patch_path = root / Path(file_path)
        entries: list[LocaleEntry] = []

        with patch_path.open("r", encoding=encoding, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:

                row["aliases"] = _unpack_aliases(row.get("aliases"))

                if row.get("lon"): row["lon"] = float(row["lon"])
                if row.get("lat"): row["lat"] = float(row["lat"])
                if row.get("cid"): row["cid"] = int(row["cid"])

                entries.append(deserialize(row, LocaleEntry))

        return entries

    @classmethod
    def dump_patch(
        cls,
        objs: Sequence[LocaleEntry],
        file_path: Path | str,
        root: Path | None = None,
        encoding: str = "utf-8",
    ) -> None:
        """Write a sequence of LocaleEntry patches to CSV via serialize()."""
        if root is None:
            raise ValueError("root must not be None")

        patch_path = root / Path(file_path)

        entries = [serialize(obj) for obj in objs]
        if not entries:
            raise ValueError("No data to write in dump_patch()")

        for row in entries:
            row["aliases"] = _pack_aliases(row.get("aliases"))

        fieldnames = list(entries[0].keys())

        with patch_path.open("w", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(entries)

    # ------------------------------------------------------------------ #
    # Lookup API
    # ------------------------------------------------------------------ #

    def search_direction(self, text: str) -> DirectionEntry | None:
        """
        Match direction by name or alias.
        Supports slight natural-language variants.
        """
        key = normalize_location_key(text)

        # direct alias match
        d = self._direction_by_alias.get(key)
        if d:
            return d

        # allow "kupyansk direction"
        if key.endswith(" direction"):
            base = key[:-10].strip()
            return self._direction_by_alias.get(base)

        # allow "direction of kupyansk"
        if key.startswith("direction of "):
            base = key[len("direction of "):].strip()
            return self._direction_by_alias.get(base)

        return None

    def search_locale(self, text: str) -> List[LocaleEntry]:
        key = normalize_location_key(text)
        return list(self._locale_by_alias.get(key, []))

    def search_region(self, text: str) -> RegionEntry | None:
        key = normalize_location_key(text)
        reg = self._region_by_alias.get(key)
        if reg is not None:
            return reg

        for suffix in (" oblast", " region"):
            if key.endswith(suffix):
                base = key[: -len(suffix)]
                reg = self._region_by_alias.get(base)
                if reg is not None:
                    return reg

        return None

    def locales_in_region(self, region_text: str) -> List[LocaleEntry]:
        region_key = normalize_location_key(region_text)
        return list(self._locale_by_region.get(region_key, []))

    def search_locale_in_region(
        self, text: str, region_text: str | None
    ) -> List[LocaleEntry]:
        if region_text is None:
            return self.search_locale(text)

        region_key = normalize_location_key(region_text)
        candidates = self.search_locale(text)
        return [
            loc for loc in candidates
            if loc.region and normalize_location_key(loc.region) == region_key
        ]

    def search_locale_in_ru_group(
        self, text: str, ru_group: str | None
    ) -> List[LocaleEntry]:
        if ru_group is None:
            return self.search_locale(text)
        ru_group = ru_group.strip()
        return [
            loc for loc in self.search_locale(text)
            if loc.ru_group == ru_group
        ]

    def has_locale(self, text: str) -> bool:
        return bool(self.search_locale(text))

    def has_region(self, text: str) -> bool:
        return self.search_region(text) is not None

    def dump_aliases(self, key: str | None = None) -> List[str]:
        if key is None or key == "all":
            entries = self.locales + self.regions
        else:
            entries = getattr(self, key, None)
            if entries is None:
                raise AttributeError(
                    f"Invalid key for dump_aliases: {key!r}. "
                    "Valid keys are 'locales', 'regions', or 'all'"
                )
        return [alias for entry in entries for alias in entry.aliases]

    # ------------------------------------------------------------------ #
    # Geospatial Utilities (Nearest Neighbor Search)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Very fast Haversine implementation."""
        R = 6371.0
        lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (math.sin(dlat/2)**2 +
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
        return R * 2 * math.asin(math.sqrt(a))

    def nearest_locale(self, lat: float, lon: float):
        """Return the nearest LocaleEntry to the given coordinate."""
        best = None
        best_dist = float("inf")
        for loc in self.locales:
            d = self._haversine_km(lat, lon, loc.lat, loc.lon)
            if d < best_dist:
                best = loc
                best_dist = d
        return best, best_dist

    def nearest_locale_by_cid(self, cid: int):
        """Nearest locale to the decoded coordinate."""
        lat, lon = decode_coord_u64(cid)
        return self.nearest_locale(lat, lon)

    def nearest_locales(self, lat: float, lon: float, n: int = 5):
        """Return N nearest locales."""
        scored = [
            (self._haversine_km(lat, lon, loc.lat, loc.lon), loc)
            for loc in self.locales
        ]
        scored.sort(key=lambda t: t[0])
        return scored[:n]

    def nearest_locales_within(self, lat: float, lon: float, km: float):
        """Return all locales within `km` radius."""
        out = []
        for loc in self.locales:
            d = self._haversine_km(lat, lon, loc.lat, loc.lon)
            if d <= km:
                out.append((d, loc))
        return sorted(out, key=lambda t: t[0])

    # ------------------------------------------------------------------ #
    # Nearest locale among same-name / alias matches
    # ------------------------------------------------------------------ #

    def get_locales_by_name(self, name: str) -> List[LocaleEntry]:
        """Return all locales whose name or aliases match `name`."""
        key = normalize_location_key(name)
        return list(self._locale_by_alias.get(key, []))

    def nearest_locale_with_name(self, name: str, lat: float, lon: float):
        """
        Find the locale with name/alias matching `name` closest to the coord.
        """
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
        """
        Same as above, but uses another LocaleEntry as the reference point.
        """
        lat0, lon0 = source_locale.lat, source_locale.lon
        candidates = self.get_locales_by_name(name)
        if not candidates:
            return None, None

        best = None
        best_dist = float("inf")

        for loc in candidates:
            if loc.cid == source_locale.cid:
                continue  # skip self
            d = self._haversine_km(lat0, lon0, loc.lat, loc.lon)
            if d < best_dist:
                best = loc
                best_dist = d

        if best is None and len(candidates) == 1:
            return candidates[0], 0.0

        return best, best_dist

    def nearest_locale_with_name_from_cid(self, name: str, cid: int):
        """Same-name nearest lookup from CID."""
        lat, lon = decode_coord_u64(cid)
        return self.nearest_locale_with_name(name, lat, lon)
