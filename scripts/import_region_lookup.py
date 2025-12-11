# scripts/import_region_lookup.py
from __future__ import annotations
import csv
from sitrepc2.config.paths import source_region_lookup_path

def import_regions(conn):
    path = source_region_lookup_path()
    print(f"📥 Importing region data...")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            conn.execute(
                """
                INSERT INTO regions (osm_id, wikidata, iso3166_2, name, aliases, neighbors)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(r["osm_id"]),
                    r["wikidata"],
                    r["iso3166_2"],
                    r["name"],
                    r["aliases"],
                    r["neighbors"],
                ),
            )

    print(f"Imported regions from {path}")
