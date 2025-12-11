# scripts/import_region_lookup.py
from __future__ import annotations

import csv
from typing import Optional

from sitrepc2.config.paths import source_region_lookup_path


def _parse_int(value: str) -> Optional[int]:
    value = (value or "").strip()
    if not value:
        return None
    return int(value)


def import_regions(conn) -> None:
    """
    Import regions from region_lookup.csv into:

      - regions(osm_id, wikidata, iso3166_2, name, aliases, neighbors)
    """
    path = source_region_lookup_path()
    print(f"📥 Importing region data from {path} ...")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required_fields = {
            "osm_id",
            "wikidata",
            "iso3166_2",
            "name",
            "aliases",
            "neighbors",
        }
        missing = required_fields.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"region_lookup.csv is missing required columns: {', '.join(sorted(missing))}"
            )

        for row in reader:
            osm_id = _parse_int(row.get("osm_id", ""))
            if osm_id is None:
                # Skip incomplete rows
                continue

            name = (row.get("name") or "").strip()
            if not name:
                raise ValueError(f"Row for osm_id={osm_id!r} is missing 'name'")

            wikidata = (row.get("wikidata") or "").strip() or None
            iso3166_2 = (row.get("iso3166_2") or "").strip() or None
            aliases = (row.get("aliases") or "").strip() or None
            neighbors = (row.get("neighbors") or "").strip() or None

            conn.execute(
                """
                INSERT INTO regions (
                    osm_id, wikidata, iso3166_2, name, aliases, neighbors
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    osm_id,
                    wikidata,
                    iso3166_2,
                    name,
                    aliases,
                    neighbors,
                ),
            )

    print("✅ Region import complete.")
