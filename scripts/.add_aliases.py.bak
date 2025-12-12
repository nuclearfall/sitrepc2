#!/usr/bin/env python3
"""
Add English-only aliases to locale_lookup.csv using a spatial GeoJSON file.

Guarantees:
- NO Cyrillic aliases remain in the output.
- All English names, including the canonical `name` field, appear in aliases
  (if they are Latin-only).
- Canonical `name` is NOT modified.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set

from sitrepc2.reference.exonyms import (
    ru_to_roman,
    uk_roman_to_ru_exonym,
    normalized_exonym_for_alias,
)
from sitrepc2.util.normalize import normalize_location_key  # imported but not used, harmless


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
SEMI_SPLIT_RE = re.compile(r"\s*;\s*")


def is_latin_only(s: str) -> bool:
    """True if string contains NO Cyrillic at all."""
    if not s:
        return False
    return not CYRILLIC_RE.search(s)


def split_semi(s: str | None) -> List[str]:
    """Split semicolon-separated values; strip empties."""
    if not s:
        return []
    return [p.strip() for p in SEMI_SPLIT_RE.split(s) if p.strip()]


# ---------------------------------------------------------------------------
# GeoJSON loader → QID→names mapping
# ---------------------------------------------------------------------------

def load_geojson(path: Path) -> Dict[str, Dict[str, List[str]]]:
    """
    Returns:
        {
          QID: {
            "ua": [...],      # Ukrainian names (generic + name:uk)
            "ru": [...],      # Russian Cyrillic names
            "en": [...],      # English names (Latin-only)
            "aliases": [...], # English-only aliases[] from spatial file
          }
        }
    """
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)

    out: Dict[str, Dict[str, List[str]]] = {}

    for feat in data.get("features", []):
        props = feat.get("properties", {}) or {}
        qid = (props.get("wikidata") or "").strip()
        if not qid:
            continue

        bucket = out.setdefault(qid, {"ua": [], "ru": [], "en": [], "aliases": []})

        # Ukrainian (generic fields, often Cyrillic)
        for key in ("name", "old_name", "alt_name"):
            bucket["ua"].extend(split_semi(props.get(key)))

        # Explicit Ukrainian variants
        for key in ("name:uk", "old_name:uk", "alt_name:uk"):
            bucket["ua"].extend(split_semi(props.get(key)))

        # Russian Cyrillic
        for key in ("name:ru", "old_name:ru", "alt_name:ru"):
            bucket["ru"].extend(split_semi(props.get(key)))

        # English (Latin-only)
        for key in ("name:en", "old_name:en", "alt_name:en"):
            for s in split_semi(props.get(key)):
                if is_latin_only(s):
                    bucket["en"].append(s)

        # English-only aliases[] array
        arr = props.get("aliases") or []
        if isinstance(arr, list):
            for a in arr:
                if isinstance(a, str) and is_latin_only(a):
                    bucket["aliases"].append(a.strip())

        # Dedupe each list
        for lang in bucket:
            uniq: List[str] = []
            seen: Set[str] = set()
            for x in bucket[lang]:
                if x and x not in seen:
                    uniq.append(x)
                    seen.add(x)
            bucket[lang] = uniq

    return out


# ---------------------------------------------------------------------------
# Main enrichment routine
# ---------------------------------------------------------------------------

def enrich_locales(
    lookup_path: Path,
    spatial_path: Path,
    out_path: Path | None,
    ru_out_path: Path | None,
) -> None:

    spatial_map = load_geojson(spatial_path)

    # Load lookup CSV
    with lookup_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        fieldnames = reader.fieldnames
        if not fieldnames or "aliases" not in fieldnames:
            raise ValueError("locale_lookup.csv must contain an 'aliases' column")
        rows = list(reader)

    ru_debug_rows: List[Dict[str, Any]] = []

    # Process each locale row
    for row in rows:
        qid = (row.get("wikidata") or "").strip()
        bucket = spatial_map.get(qid)  # may be None if no spatial data

        if bucket is not None:
            ua_names = bucket["ua"]      # mostly Cyrillic, only used if Latin
            ru_names = bucket["ru"]      # Cyrillic, only used via transliteration
            en_names = bucket["en"]      # English (Latin-only)
            alias_arr = bucket["aliases"]  # English-only from spatial
        else:
            ua_names = []
            ru_names = []
            en_names = []
            alias_arr = []

        canonical_name = (row.get("name") or "").strip()

        # -------------------------------------------------------------------
        # ALWAYS rebuild aliases: start from existing, DROP all Cyrillic ones
        # -------------------------------------------------------------------
        existing_aliases_raw = [
            a.strip()
            for a in str(row.get("aliases") or "").split(";")
            if a.strip()
        ]

        new_aliases: Set[str] = set()    # raw aliases to keep/add
        seen_norm: Set[str] = set()      # normalized aliases for dedupe

        def _try_add_alias(raw: str) -> None:
            """Add a candidate alias if it's Latin-only and not a normalized duplicate."""
            if not raw:
                return
            if not is_latin_only(raw):
                return
            norm = normalized_exonym_for_alias(raw)
            if not norm:
                return
            if norm in seen_norm:
                return
            seen_norm.add(norm)
            new_aliases.add(raw)

        # 1) Existing aliases → keep only Latin-only
        for alias in existing_aliases_raw:
            _try_add_alias(alias)

        # 2) Ensure canonical name is in aliases (if Latin-only)
        _try_add_alias(canonical_name)

        # If we *do* have spatial data, augment with more info
        if bucket is not None:
            # 3) Add all English names from spatial file
            for s in en_names:
                _try_add_alias(s)

            # 4) Add English-only spatial aliases[]
            for s in alias_arr:
                _try_add_alias(s)

            # 5) Add English transliterations of Russian Cyrillic names
            for ru in ru_names:
                if not ru:
                    continue
                tr = ru_to_roman(ru)
                _try_add_alias(tr)

            # 6) Add Russian-style English exonyms derived from Ukrainian *romanized* names
            for ua in ua_names:
                # Only use UA names that are already Latin (e.g., from prior romanization)
                if not ua or not is_latin_only(ua):
                    continue
                ex = uk_roman_to_ru_exonym(ua)
                if not ex:
                    continue
                for part in split_semi(ex):
                    _try_add_alias(part)

        # Set final alias string (sorted for stability)
        row["aliases"] = ";".join(sorted(new_aliases))

        # Optional debug record
        if ru_out_path:
            ru_debug_rows.append({
                "wikidata": qid,
                "canonical_name": canonical_name,
                "ua_names": ", ".join(ua_names),
                "ru_names": ", ".join(ru_names),
                "en_names": ", ".join(en_names),
                "spatial_aliases": ", ".join(alias_arr),
                "final_aliases": row["aliases"],
            })

    # Write updated lookup CSV
    target = out_path if out_path else lookup_path
    with target.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Enriched locale_lookup.csv → {target}")

    # Optional debug CSV
    if ru_out_path:
        with ru_out_path.open("w", encoding="utf-8", newline="") as fp:
            writer = csv.DictWriter(
                fp,
                fieldnames=[
                    "wikidata",
                    "canonical_name",
                    "ua_names",
                    "ru_names",
                    "en_names",
                    "spatial_aliases",
                    "final_aliases",
                ],
            )
            writer.writeheader()
            writer.writerows(ru_debug_rows)
        print(f"✓ Wrote debug ru_exo CSV → {ru_out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lookup",
        type=Path,
        required=True,
        help="Path to locale_lookup.csv",
    )
    parser.add_argument(
        "--spatial",
        type=Path,
        required=True,
        help="Path to spatial GeoJSON file (Overpass result).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional output CSV. If omitted, updates lookup in place.",
    )
    parser.add_argument(
        "--ru_out",
        type=Path,
        default=None,
        help="Optional debug CSV with ru/ua/en names and final aliases.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    enrich_locales(
        lookup_path=args.lookup,
        spatial_path=args.spatial,
        out_path=args.out,
        ru_out_path=args.ru_out,
    )


if __name__ == "__main__":
    main()
