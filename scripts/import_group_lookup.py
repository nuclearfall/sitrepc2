# scripts/import_group_lookup.py
from __future__ import annotations

import csv
from typing import Optional

from sitrepc2.config.paths import source_group_lookup_path


def _parse_int(value: str) -> Optional[int]:
    value = (value or "").strip()
    if not value:
        return None
    return int(value)


def import_groups(conn) -> None:
    """
    Import groups from group_lookup.csv into:

      - groups(group_id, name, aliases, region_ids, neighbor_ids)

    The CSV is expected to have headers:

      name,group_id,aliases,region_ids,neighbor_ids
    """
    path = source_group_lookup_path()
    print(f"📥 Importing group data from {path} ...")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required_fields = {
            "name",
            "group_id",
            "aliases",
            "region_ids",
            "neighbor_ids",
        }
        missing = required_fields.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"group_lookup.csv is missing required columns: {', '.join(sorted(missing))}"
            )

        for row in reader:
            group_id = _parse_int(row.get("group_id", ""))
            if group_id is None:
                # group_id is PK; skip incomplete rows
                continue

            name = (row.get("name") or "").strip()
            if not name:
                raise ValueError(f"Row for group_id={group_id!r} is missing 'name'")

            aliases = (row.get("aliases") or "").strip() or None
            region_ids = (row.get("region_ids") or "").strip() or None
            neighbor_ids = (row.get("neighbor_ids") or "").strip() or None

            conn.execute(
                """
                INSERT INTO groups (
                    group_id, name, aliases, region_ids, neighbor_ids
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    group_id,
                    name,
                    aliases,
                    region_ids,
                    neighbor_ids,
                ),
            )

    print("✅ Group import complete.")
