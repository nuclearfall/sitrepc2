# scripts/import_group_lookup.py
from __future__ import annotations
import csv
from sitrepc2.config.paths import source_group_lookup_path

def import_groups(conn):
    path = source_group_lookup_path()
    print(f"📥 Importing group data...")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for g in reader:
            conn.execute(
                """
                INSERT INTO groups (group_id, name, aliases, neighbor_groups, regions)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(g["group_id"]),
                    g["name"],
                    g["aliases"],
                    g["neighbors"],
                    g["regions"],
                ),
            )

    print(f"Imported groups from {path}")
