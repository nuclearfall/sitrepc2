# scripts/import_locale_lookup.py
from __future__ import annotations
import csv
from pathlib import Path
from sitrepc2.config.paths import source_locale_lookup_path

def normalize(s: str) -> str:
    return s.lower().strip()

def import_locales(conn):
    path = source_locale_lookup_path()
    print(f"📥 Importing locale data...")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row["cid"]

            conn.execute(
                """
                INSERT INTO locales (cid, name, place, wikidata, group_id, lon, lat, region_osm_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    row["name"],
                    row["place"],
                    row["wikidata"] if row["wikidata"] != "none" else None,
                    int(row["group_id"]) if row["group_id"] else None,
                    float(row["lon"]),
                    float(row["lat"]),
                    int(row["region_osm_id"]) if row["region_osm_id"] else None,
                ),
            )

            # aliases
            aliases = row["aliases"].split(";")
            for alias in aliases:
                alias = alias.strip()
                if alias:
                    conn.execute(
                        """
                        INSERT INTO aliases (entity_type, entity_id, alias, normalized)
                        VALUES ('locale', ?, ?, ?)
                        """,
                        (cid, alias, normalize(alias)),
                    )

    print(f"Imported locales from {path}")

