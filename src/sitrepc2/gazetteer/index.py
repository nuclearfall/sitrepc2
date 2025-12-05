# src/modmymap/gazetteer/index.py
from __future__ import annotations

import ast
import csv
from dataclasses import dataclass
from pathlib import Path
from normalize import normalize_location_key
from modmymap.util.normalization import normalize_location_key


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LocaleEntry:
    """
    One row from locale_lookup.csv.

    Expected header:
        name, aliases, place, wikidata, coordinates, region, ru_group, usage
    """

    name: str
    aliases: list[str]
    place: str
    wikidata: str | None
    lon: float | None
    lat: float | None
    region: str | None         # parent oblast
    ru_group: str | None       # Russian operational group
    usage: int

    @classmethod
    def from_row(cls, row: dict) -> "LocaleEntry":
        raw_aliases = row.get("aliases", "") or ""
        aliases = [a.strip() for a in raw_aliases.split(";") if a.strip()]

        name = (row.get("name") or "").strip()
        if name:
            norm_name = normalize_location_key(name)
            if norm_name not in aliases:
                aliases.append(norm_name)

        coords_str = (row.get("coordinates") or "").strip()
        lat = lon = None
        if coords_str:
            try:
                coords = ast.literal_eval(coords_str)
                if (
                    isinstance(coords, (list, tuple))
                    and len(coords) == 2
                    and all(isinstance(x, (int, float)) for x in coords)
                ):
                    lon = float(coords[0])
                    lat = float(coords[1])
            except Exception:
                pass

        wikidata = (row.get("wikidata") or "").strip() or None
        region = (row.get("region") or "").strip() or None
        ru_group = (row.get("ru_group") or "").strip() or None

        usage_str = (row.get("usage") or "").strip()
        try:
            usage = int(usage_str) if usage_str else 0
        except ValueError:
            usage = 0

        place = (row.get("place") or "").strip()

        return cls(
            name=name,
            aliases=aliases,
            place=place,
            wikidata=wikidata,
            lat=lat,
            lon=lon,
            region=region,
            ru_group=ru_group,
            usage=usage,
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "aliases": self.aliases,
            "place": self.place,
            "wikidata": self.wikidata,
            "lat": self.lat,
            "lon": self.lon,
            "region": self.region,
            "ru_group": self.ru_group,
            "usage": self.usage,
        }


@dataclass
class RegionEntry:
    """
    One row from region_lookup.csv — but now ALWAYS a single region per alias.

    We no longer support lists of region candidates.
    """

    wikidata: str | None
    iso3166_2: str | None
    name: str                 # canonical English name
    aliases: list[str]        # all normalized alias keys (including name)
    source: str | None

    @classmethod
    def from_row(cls, row: dict) -> "RegionEntry":
        raw_aliases = row.get("aliases", "") or ""
        aliases = [a.strip() for a in raw_aliases.split(";") if a.strip()]

        name = (row.get("name") or "").strip()
        if name:
            norm = normalize_location_key(name)
            if norm not in aliases:
                aliases.append(norm)

        wikidata = (row.get("wikidata") or "").strip() or None
        iso3166_2 = (row.get("iso3166_2") or "").strip() or None
        source = (row.get("source") or "").strip() or None

        return cls(
            wikidata=wikidata,
            iso3166_2=iso3166_2,
            name=name,
            aliases=aliases,
            source=source,
        )

    def to_dict(self) -> dict:
        return {
            "wikidata": self.wikidata,
            "iso3166_2": self.iso3166_2,
            "name": self.name,
            "aliases": self.aliases,
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# Gazetteer index
# ---------------------------------------------------------------------------


class GazetteerIndex:
    """
    In-memory index for locales and regions.

    PHASE 1 changes:
      - Region aliases now map to EXACTLY ONE RegionEntry.
      - search_region() returns RegionEntry | None (NOT a list).
      - Duplicate region aliases raise an error at load time.
    """

    def __init__(
        self,
        locales: list[LocaleEntry],
        regions: list[RegionEntry],
    ) -> None:
        self.locales = locales
        self.regions = regions

        # alias_key -> list[LocaleEntry]
        self._locale_by_alias: dict[str, list[LocaleEntry]] = {}

        # alias_key -> RegionEntry  (NOT list)
        self._region_by_alias: dict[str, RegionEntry] = {}

        # region_key -> list[LocaleEntry]
        self._locale_by_region: dict[str, list[LocaleEntry]] = {}

        self._build_indexes()

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

        # --- regions: enforce UNIQUE alias → single RegionEntry
        for reg in self.regions:
            for alias in reg.aliases:
                key = normalize_location_key(alias)
                if key in self._region_by_alias:
                    raise ValueError(
                        f"Duplicate region alias '{alias}' mapping to multiple regions: "
                        f"{self._region_by_alias[key].name!r} and {reg.name!r}"
                    )
                self._region_by_alias[key] = reg

    # ------------------------------------------------------------------ #

    @classmethod
    def from_csv_files(
        cls,
        locale_path: Path = Path("data/gazetteer/locale_lookup.csv"),
        region_path: Path = Path("data/gazetteer/region_lookup.csv"),
        encoding: str = "utf-8",
    ) -> "GazetteerIndex":
        locales: list[LocaleEntry] = []
        regions: list[RegionEntry] = []

        with locale_path.open("r", encoding=encoding, newline="") as f:
            for row in csv.DictReader(f):
                locales.append(LocaleEntry.from_row(row))

        with region_path.open("r", encoding=encoding, newline="") as f:
            for row in csv.DictReader(f):
                regions.append(RegionEntry.from_row(row))

        return cls(locales=locales, regions=regions)

    # ------------------------------------------------------------------ #
    # Lookup API
    # ------------------------------------------------------------------ #

    def search_locale(self, text: str) -> list[LocaleEntry]:
        key = normalize_location_key(text)
        return list(self._locale_by_alias.get(key, []))

    def search_region(self, text: str) -> RegionEntry | None:
        """
        Return EXACTLY ONE region match (or None).

        Handles "X oblast"/"X region" by stripping the suffix if needed,
        so that aliases like "dnepropetrovsk" match "Dnepropetrovsk region".
        """
        key = normalize_location_key(text)
        reg = self._region_by_alias.get(key)
        if reg is not None:
            return reg

        # Fallback: strip common suffixes and try again.
        for suffix in (" oblast", " region"):
            if key.endswith(suffix):
                base = key[: -len(suffix)]
                reg = self._region_by_alias.get(base)
                if reg is not None:
                    return reg

        return None

    # ---------------------------------------------

    def locales_in_region(self, region_text: str) -> list[LocaleEntry]:
        region_key = normalize_location_key(region_text)
        return list(self._locale_by_region.get(region_key, []))

    def search_locale_in_region(
        self, text: str, region_text: str | None
    ) -> list[LocaleEntry]:
        if region_text is None:
            return self.search_locale(text)

        region_key = normalize_location_key(region_text)
        candidates = self.search_locale(text)
        return [
            loc for loc in candidates
            if loc.region and normalize_location_key(loc.region) == region_key
        ]

    # ---------------------------------------------

    def search_locale_in_ru_group(
        self, text: str, ru_group: str | None
    ) -> list[LocaleEntry]:
        if ru_group is None:
            return self.search_locale(text)
        ru_group = ru_group.strip()
        return [
            loc for loc in self.search_locale(text)
            if loc.ru_group == ru_group
        ]

    # ---------------------------------------------

    def has_locale(self, text: str) -> bool:
        return bool(self.search_locale(text))

    def has_region(self, text: str) -> bool:
        return self.search_region(text) is not None
