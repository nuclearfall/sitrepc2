#!/usr/bin/env python3
"""
Build + append Russian exonyms and transliterations to locale_lookup.csv
in a single unified workflow.

CLI Usage:
    python build_and_append_exonyms.py \
        --wiki latest-all.json.bz2 \
        --lookup src/sitrepc2/reference/locale_lookup.csv \
        --ru_out ru_exo.csv \
        --out updated_locale_lookup.csv

Arguments:
    --wiki     Path to Wikidata dump (latest-all.json.bz2)
    --lookup   Path to locale_lookup.csv
    --ru_out   Optional output path for extracted ru_exo.csv
    --out      Optional output path for updated locale_lookup.csv
               If omitted, edits are applied IN PLACE.
"""

from __future__ import annotations

import argparse
import bz2
import csv
import json
import re
from pathlib import Path
from typing import Dict, Any, List

# Import your existing exonym utilities
from sitrepc2.reference.exonyms import (
    uk_roman_to_ru_exonym,
    ru_to_roman,
    normalized_exonym_for_alias,
)
from sitrepc2.util.normalize import normalize_location_key


# ---------------------------------------------------------------------------
# Your normalization rules for canonical comparison
# ---------------------------------------------------------------------------

def normalize_for_compare(s: str) -> str:
    """
    Your normalization:
    - remove parentheses and contents
    - remove apostrophes
    - replace hyphens with space
    - trim + collapse whitespace
    """
    if not s:
        return ""

    # Remove ( ... )
    s = re.sub(r"\s*\([^)]*\)", "", s)

    # Remove apostrophes
    s = s.replace("'", "").replace("’", "")

    # Replace hyphens
    s = s.replace("-", " ")

    # Collapse whitespace
    s = " ".join(s.split()).strip()

    return s


# ---------------------------------------------------------------------------
# Stream Wikidata dump
# ---------------------------------------------------------------------------

def load_wikidata_labels(path: Path) -> Dict[str, Dict[str, str]]:
    """
    Stream Wikidata dump (latest-all.json.bz2, full or filtered).
    Extract only:
        name:en, name:uk, name:ru

    Returns dict:
        { QID: {"en": ..., "uk": ..., "ru": ...} }
    """
    print(f"Scanning Wikidata dump: {path}")
    out: Dict[str, Dict[str, str]] = {}

    with bz2.open(path, "rt", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip().rstrip(",")
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue

            qid = obj.get("id")
            if not qid or not qid.startswith("Q"):
                continue

            labels = obj.get("labels", {})
            if not labels:
                continue

            out[qid] = {
                "en": labels.get("en", {}).get("value", "") or "",
                "uk": labels.get("uk", {}).get("value", "") or "",
                "ru": labels.get("ru", {}).get("value", "") or "",
            }

    print(f"Loaded label data for {len(out)} entities.")
    return out


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append Russian exonyms to locale_lookup.csv")

    p.add_argument(
        "--wiki",
        type=Path,
        required=True,
        help="Path to latest-all.json.bz2 (Wikidata dump).",
    )
    p.add_argument(
        "--lookup",
        type=Path,
        required=True,
        help="Path to locale_lookup.csv.",
    )
    p.add_argument(
        "--ru_out",
        type=Path,
        default=None,
        help="Optional CSV to write (wikidata,name:ru,name:uk,name:en,replace_canonical).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write updated locale_lookup.csv. "
             "If omitted, edits in-place.",
    )

    return p.parse_args()


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    wiki_path = args.wiki
    lookup_path = args.lookup
    ru_out_path = args.ru_out
    out_path = args.out or lookup_path  # edit in place if no output was provided

    if not wiki_path.is_file():
        raise FileNotFoundError(f"--wiki file not found: {wiki_path}")

    if not lookup_path.is_file():
        raise FileNotFoundError(f"--lookup file not found: {lookup_path}")

    # -------------------------------------------------------------------
    # Load locale_lookup.csv
    # -------------------------------------------------------------------
    print(f"Loading locale_lookup.csv: {lookup_path}")

    rows: List[dict[str, Any]] = []
    with lookup_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise ValueError("CSV missing header row.")
        for row in reader:
            rows.append(row)

    # -------------------------------------------------------------------
    # Load Wikidata labels
    # -------------------------------------------------------------------
    wd_labels = load_wikidata_labels(wiki_path)

    # For optional ru_exo.csv output:
    ru_records: List[dict[str, str]] = []

    # -------------------------------------------------------------------
    # Process each settlement
    # -------------------------------------------------------------------
    print("Processing rows...")

    for row in rows:
        canonical = (row.get("name") or "").strip()
        qid = (row.get("wikidata") or "").strip()

        aliases_str = str(row.get("aliases") or "")
        aliases_raw = [a.strip() for a in aliases_str.split(";") if a.strip()]
        normalized_existing = {normalized_exonym_for_alias(a) for a in aliases_raw}

        name_en = name_uk = name_ru = ""
        if qid and qid in wd_labels:
            name_en = wd_labels[qid]["en"]
            name_uk = wd_labels[qid]["uk"]
            name_ru = wd_labels[qid]["ru"]

        # ---------------------------------------------------------------
        # 1) Canonical replacement detection
        # ---------------------------------------------------------------
        replace_flag = False
        if name_en:
            if normalize_for_compare(name_en) != normalize_for_compare(canonical):
                replace_flag = True
                row["name"] = name_en

        # ---------------------------------------------------------------
        # 2) Collect Russian exonyms + transliterations
        # ---------------------------------------------------------------
        exonyms_to_add: List[str] = []

        # A) Transliteration of Russian Cyrillic into Latin
        if name_ru:
            ex1 = ru_to_roman(name_ru)
            if ex1:
                exonyms_to_add.append(ex1)

        # B) Russian-style exonyms derived from Ukrainian romanization
        if name_uk:
            ex2 = uk_roman_to_ru_exonym(name_uk)
            if ex2:
                for part in ex2.split(";"):
                    if part.strip():
                        exonyms_to_add.append(part.strip())

        # Insert into aliases if new
        for ex in exonyms_to_add:
            norm_ex = normalized_exonym_for_alias(ex)
            if norm_ex and norm_ex not in normalized_existing:
                aliases_raw.append(norm_ex)
                normalized_existing.add(norm_ex)

        row["aliases"] = ";".join(aliases_raw)

        # Save ru_exo row if requested
        if ru_out_path:
            ru_records.append({
                "wikidata": qid,
                "name:ru": name_ru,
                "name:uk": name_uk,
                "name:en": name_en,
                "replace_canonical": "true" if replace_flag else "false",
            })

    # -------------------------------------------------------------------
    # Optional: write ru_exo.csv
    # -------------------------------------------------------------------
    if ru_out_path:
        print(f"Writing ru_exo.csv → {ru_out_path}")
        with ru_out_path.open("w", encoding="utf-8", newline="") as fp:
            fieldnames_ru = ["wikidata", "name:ru", "name:uk", "name:en", "replace_canonical"]
            writer = csv.DictWriter(fp, fieldnames=fieldnames_ru)
            writer.writeheader()
            writer.writerows(ru_records)

    # -------------------------------------------------------------------
    # Write updated locale_lookup.csv
    # -------------------------------------------------------------------
    print(f"Writing updated locale lookup → {out_path}")

    with out_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("✔ Done.")


if __name__ == "__main__":
    main()
