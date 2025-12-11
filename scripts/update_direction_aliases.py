#!/usr/bin/env python3
"""
Update direction_lookup.csv by adding English-only aliases from locale_lookup.csv.

Rules:
- Directions must have unique CIDs. If duplicates exist, keep only the first.
- Canonical name always comes from locale_lookup.csv.
- New column `aliases` is added containing English-only, normalized aliases.
- No Cyrillic is included.
- normalize_location_key is applied to all aliases.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Set

import pandas as pd

from sitrepc2.util.normalize import normalize_location_key


# ---------------------------
# Cyrillic detection
# ---------------------------

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def is_latin_only(s: str) -> bool:
    """Return True if no Cyrillic characters appear."""
    return bool(s) and not CYRILLIC_RE.search(s)


def normalize_alias(a: str) -> str:
    """Normalize using normalize_location_key and enforce Latin-only."""
    if not a:
        return ""
    if not is_latin_only(a):
        return ""
    return normalize_location_key(a)


# ---------------------------
# Main enrichment procedure
# ---------------------------

def update_directions(
    lookup_path: Path,
    directions_path: Path,
    out_path: Path,
) -> None:

    # ---------------------------
    # Load lookup + directions
    # ---------------------------
    lookup = pd.read_csv(lookup_path, dtype=str).fillna("")
    dire = pd.read_csv(directions_path, dtype=str).fillna("")

    if "cid" not in lookup.columns or "cid" not in dire.columns:
        raise ValueError("Both lookup and directions CSV files must contain a 'cid' column.")

    # ---------------------------
    # Auto-remove duplicate direction CIDs
    # ---------------------------
    dire = dire.drop_duplicates(subset=["cid"], keep="first").reset_index(drop=True)

    # ---------------------------
    # Prepare lookup table with renamed alias column
    # ---------------------------
    lookup2 = lookup.rename(columns={"aliases": "lookup_aliases"})

    # ---------------------------
    # Merge direction entries with lookup rows on CID
    # ---------------------------
    merged = dire.merge(
        lookup2[["cid", "name", "lookup_aliases"]],
        how="left",
        on="cid",
        validate="1:1"
    )

    # Determine canonical name column
    # After merge, lookup.name becomes `name_y` if directions also has `name`.
    if "name_y" in merged.columns:
        canon_col = "name_y"
    elif "name" in merged.columns:
        canon_col = "name"
    else:
        raise ValueError("Could not find canonical name column after merge.")

    # ---------------------------
    # Build final aliases for each direction entry
    # ---------------------------
    final_aliases: List[List[str]] = []

    for _, row in merged.iterrows():
        # Lookup aliases (safe)
        raw_aliases = str(row.get("lookup_aliases", "") or "").split(";")

        # Canonical name from lookup
        canonical = str(row.get(canon_col, "") or "").strip()

        alias_set: Set[str] = set()

        # 1. Add canonical name
        norm = normalize_alias(canonical)
        if norm:
            alias_set.add(norm)

        # 2. Add normalized lookup aliases
        for a in raw_aliases:
            norm = normalize_alias(a.strip())
            if norm:
                alias_set.add(norm)

        final_aliases.append(sorted(alias_set))

    # Store clean alias strings
    merged["aliases"] = [";".join(a) for a in final_aliases]

    # Remove helper columns
    if "name_y" in merged.columns:
        merged = merged.drop(columns=["name_y"])
    if "lookup_aliases" in merged.columns:
        merged = merged.drop(columns=["lookup_aliases"])

    # ---------------------------
    # Write output
    # ---------------------------
    merged.to_csv(out_path, index=False)
    print(f"✓ Updated directions (duplicates removed, aliases added) → {out_path}")



# ---------------------------
# CLI interface
# ---------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lookup",
        required=True,
        type=Path,
        help="Path to locale_lookup.csv"
    )
    parser.add_argument(
        "--directions",
        required=True,
        type=Path,
        help="Path to direction_lookup.csv"
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output CSV path for updated direction lookup"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    update_directions(args.lookup, args.directions, args.out)


if __name__ == "__main__":
    main()
