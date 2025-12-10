"""Append Russian exonyms to ``src/sitrepc2/reference/locale_lookup.csv``.

Usage:
    python scripts/append_exonyms.py [--csv PATH] [--locales GEOJSON]

If no arguments are provided, the script updates the canonical
``src/sitrepc2/reference/locale_lookup.csv`` file in place.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sitrepc2.reference.exonyms import append_exonyms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        dest="csv_path",
        type=Path,
        default=None,
        help="Path to a locale_lookup.csv-style file. Defaults to the reference file.",
    )
    parser.add_argument(
        "--locales",
        dest="locales_path",
        type=Path,
        default=None,
        help="Optional locales GeoJSON containing name:ru entries to transliterate.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    append_exonyms(csv_path=args.csv_path, locales_path=args.locales_path)


if __name__ == "__main__":
    main()
