#!/usr/bin/env python3
"""
Normalize *all* alias entries in locale_lookup.csv using
sitrepc2.util.normalize.normalize_location_key.

This script performs:

    • Cyrillic removal
    • normalize_location_key() applied to every alias
    • deduplication after normalization
    • canonical 'name' is preserved (not normalized here)
    • writes output either in place or to --out

Usage:

    python scripts/normalize_aliases.py \
        --lookup src/sitrepc2/reference/locale_lookup.csv \
        --out locale_lookup.normalized.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from sitrepc2.util.normalize import normalize_location_key

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def is_latin_only(s: str) -> bool:
    if not s:
        return False
    return not CYRILLIC_RE.search(s)


def normalize_alias_list(raw_aliases: str) -> str:
    """
    Take the semicolon-separated alias list, remove Cyrillic entries,
    normalize via normalize_location_key(), dedupe, and return a new
    semicolon-separated list.
    """
    if not raw_aliases:
        return ""

    parts = [a.strip() for a in raw_aliases.split(";") if a.strip()]

    cleaned = set()

    for alias in parts:
        if not is_latin_only(alias):
            continue  # drop Cyrillic alias entirely

        norm = normalize_location_key(alias)
        if not norm:
            continue
        cleaned.add(norm)

    return ";".join(sorted(cleaned))


def normalize_csv(lookup_path: Path, out_path: Path | None) -> None:
    with lookup_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        fieldnames = reader.fieldnames
        if not fieldnames or "aliases" not in fieldnames:
            raise ValueError("CSV must contain an 'aliases' column")
        rows = list(reader)

    # Normalize aliases column for every row
    for row in rows:
        raw_aliases = row.get("aliases", "")
        row["aliases"] = normalize_alias_list(raw_aliases)

    # Output
    target = out_path if out_path else lookup_path
    with target.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Normalized aliases written to {target}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lookup", type=Path, required=True,
                  help="Path to locale_lookup.csv")
    p.add_argument("--out", type=Path, default=None,
                  help="Optional output CSV; overwrites lookup if omitted.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    normalize_csv(args.lookup, args.out)


if __name__ == "__main__":
    main()
