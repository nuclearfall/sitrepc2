from __future__ import annotations

import ast
import csv
from dataclasses import dataclass, field
from typing import Optional, Sequence, List, Any
from pathlib import Path

from sitrepc2.config.paths import resolve_gazetteer_paths
from sitrepc2.util.normalize import normalize_location_key


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
# Gazetteer index
# ---------------------------------------------------------------------------


class GazetteerIndex:
    """
    In-memory index for locales and regions.

    PHASE 1 changes:
      - Region aliases now map to EXACTLY ONE RegionEntry.
      - search_region() returns RegionEntry | None (NOT a List).
      - Duplicate region aliases raise an error at load time.
    """

    def __init__(
        self,
        locales: List[LocaleEntry],
        regions: List[RegionEntry],
    ) -> None:
        self.locales = locales
        self.regions = regions

        # alias_key -> List[LocaleEntry]
        self._locale_by_alias: dict[str, List[LocaleEntry]] = {}

        # alias_key -> RegionEntry  (NOT List)
        self._region_by_alias: dict[str, RegionEntry] = {}

        # region_key -> List[LocaleEntry]
        self._locale_by_region: dict[str, List[LocaleEntry]] = {}

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
    def load_canonical(
        cls,
        root: Path | None = None,
        encoding: str = "utf-8",
    ) -> "GazetteerIndex":

        out: list[list[object]] = []

        for path in resolve_gazetteer_paths(root):
            entries: list[object] = []
            with path.open("r", encoding=encoding, newline="") as f:
                for row in csv.DictReader(f):
                    row["aliases"] = _unpack_aliases(row.get("aliases"))
                    entries.append(deserialize(row))
            out.append(entries)

        locales, regions, *_ = out
        return cls(locales=locales, regions=regions)

    @classmethod
    def load_patch(
        cls,
        file_path: Path | str,
        root: Path | None = None,
        encoding: str = "utf-8",
    ) -> list["LocaleEntry"]:
        """Load a patch CSV and return a list of LocaleEntry objects."""
        if root is None:
            raise ValueError("root must not be None")

        patch_path = root / Path(file_path)
        entries: list[LocaleEntry] = []

        with patch_path.open("r", encoding=encoding, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["aliases"] = _unpack_aliases(row.get("aliases"))
                entries.append(deserialize(row))

        return entries

    @classmethod
    def dump_patch(
        cls,
        objs: Sequence["LocaleEntry"],
        file_path: Path | str,
        root: Path | None = None,
        encoding: str = "utf-8",
    ) -> None:
        """Write a sequence of LocaleEntry patches to CSV via serialize()."""
        if root is None:
            raise ValueError("root must not be None")

        patch_path = root / Path(file_path)

        # (1) serialize objects
        entries = [serialize(obj) for obj in objs]

        if not entries:
            raise ValueError("No data to write in dump_patch()")

        # (2) pack aliases into CSV-friendly string
        for row in entries:
            row["aliases"] = _pack_aliases(row.get("aliases"))

        # (3) write CSV
        fieldnames = list(entries[0].keys())

        with patch_path.open("w", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(entries)


    # ------------------------------------------------------------------ #
    # Lookup API
    # ------------------------------------------------------------------ #

    def search_locale(self, text: str) -> List[LocaleEntry]:
        key = normalize_location_key(text)
        return List(self._locale_by_alias.get(key, []))

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

    def locales_in_region(self, region_text: str) -> List[LocaleEntry]:
        region_key = normalize_location_key(region_text)
        return List(self._locale_by_region.get(region_key, []))

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

    # ---------------------------------------------

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

    # ---------------------------------------------

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
                ) from None

        return [
            alias
            for entry in entries
            for alias in entry.aliases
        ]
