# scripts/import_locale_lookup.py
from __future__ import annotations

import csv
from typing import Optional

from sitrepc2.config.paths import source_locale_lookup_path


def _normalize(s: str) -> str:
    return s.lower().strip()


def _parse_int(value: str) -> Optional[int]:
    value = (value or "").strip()
    if not value:
        return None
    return int(value)


def _parse_float(value: str) -> Optional[float]:
    value = (value or "").strip()
    if not value:
        return None
    return float(value)


def import_locales(conn) -> None:
    """
    Import locales from locale_lookup.csv into:

      - locales(cid, name, aliases, place, wikidata,
                group_id, usage, lon, lat, region_id)
      - aliases(entity_type, entity_id, alias, normalized)
        with entity_type='locale' and entity_id = cid
    """
    path = source_locale_lookup_path()
    print(f"📥 Importing locale data from {path} ...")

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required_fields = {
            "name",
            "aliases",
            "place",
            "wikidata",
            "group_id",
            "usage",
            "lon",
            "lat",
            "cid",
            "region_id",
        }
        missing = required_fields.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"locale_lookup.csv is missing required columns: {', '.join(sorted(missing))}"
            )

        for row in reader:
            cid = (row["cid"] or "").strip()
            if not cid:
                # Skip rows without a CID
                continue

            name = (row["name"] or "").strip()
            if not name:
                # Name is NOT NULL in schema; better to fail loudly than silently
                raise ValueError(f"Row for cid={cid!r} is missing 'name'")

            aliases_raw = (row.get("aliases") or "").strip()
            place = (row.get("place") or "").strip() or None
            wikidata = (row.get("wikidata") or "").strip() or None
            usage = (row.get("usage") or "").strip() or None

            group_id = _parse_int(row.get("group_id", ""))
            region_id = _parse_int(row.get("region_id", ""))
            lon = _parse_float(row.get("lon", ""))
            lat = _parse_float(row.get("lat", ""))

            # Insert into locales table
            conn.execute(
                """
                INSERT INTO locales (
                    cid, name, aliases, place, wikidata,
                    group_id, usage, lon, lat, region_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cid,
                    name,
                    aliases_raw,
                    place,
                    wikidata,
                    group_id,
                    usage,
                    lon,
                    lat,
                    region_id,
                ),
            )

            # Insert aliases into aliases table (one row per alias)
            if aliases_raw:
                for alias in aliases_raw.split(";"):
                    alias = alias.strip()
                    if not alias:
                        continue
                    conn.execute(
                        """
                        INSERT INTO aliases (entity_type, entity_id, alias, normalized)
                        VALUES ('locale', ?, ?, ?)
                        """,
                        (cid, alias, _normalize(alias)),
                    )

    print("✅ Locale import complete.")
