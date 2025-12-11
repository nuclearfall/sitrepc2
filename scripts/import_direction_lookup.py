# scripts/import_direction_lookup.py
from __future__ import annotations
import csv
from sitrepc2.config.paths import source_direction_lookup_path

def import_directions(conn):
    path = source_direction_lookup_path()
    print(f"📥 Importing direction data...")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            direction = row["direction"].strip()
            cid = row["cid"].strip()

            conn.execute(
                """
                INSERT INTO directions (direction, cid)
                VALUES (?, ?)
                """,
                (direction, cid),
            )

    print(f"Imported directions from {path}")
