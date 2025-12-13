# src/sitrepc2/gazetteer/io.py
from __future__ import annotations

from dataclasses import asdict
from typing import List, Dict, Optional, Iterable

from sitrepc2.db.core import connect
from sitrepc2.gazetteer.typedefs import (
    LocaleEntry,
    RegionEntry,
    GroupEntry,
    DirectionEntry,
)
from sitrepc2.util.serialization import deserialize


# ------------------------------
# Alias / list helpers
# ------------------------------

def unpack_aliases(s: str | None) -> List[str]:
    if not s:
        return []
    return [a.strip() for a in s.split(";") if a.strip()]


def pack_aliases(aliases: Iterable[str]) -> str:
    return ";".join(a for a in aliases if a.strip())


def unpack_int_list(s: str | None) -> List[int]:
    if not s:
        return []
    out: List[int] = []
    for part in s.split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            # Be forgiving; you can tighten this later if needed.
            continue
    return out


# ------------------------------
# Locale Loader (from DB)
# ------------------------------

def load_locales_from_db() -> List[LocaleEntry]:
    """
    Load all LocaleEntry objects from the SQLite database.

    Maps directly from the `locales` table:

        cid, name, aliases, place, wikidata,
        group_id, usage, lon, lat, region_id
    """
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT
                cid,
                name,
                aliases,
                place,
                wikidata,
                group_id,
                usage,
                lon,
                lat,
                region_id
            FROM locales
            ORDER BY name ASC
            """
        ).fetchall()

        out: List[LocaleEntry] = []
        for row in rows:
            # Build a dict aligned with LocaleEntry fields
            data = {
                "cid": str(row["cid"]),
                "name": row["name"],
                "aliases": unpack_aliases(row["aliases"]),
                "lon": float(row["lon"]) if row["lon"] is not None else 0.0,
                "lat": float(row["lat"]) if row["lat"] is not None else 0.0,
                "region_id": row["region_id"],
                "group_id": row["group_id"],
                "place": row["place"],
                "wikidata": row["wikidata"],
                # usage is stored as TEXT or NULL; coerce to int with a sane default
                "usage": int(row["usage"]) if row["usage"] not in (None, "") else 0,
                # `source` will fall back to dataclass default ("base") if omitted,
                # but we can be explicit if you like:
                # "source": "db",
            }
            out.append(deserialize(data, LocaleEntry))
        return out
    finally:
        conn.close()


# ------------------------------
# Region Loader (from DB)
# ------------------------------

def load_regions_from_db() -> List[RegionEntry]:
    """
    Load all RegionEntry objects from the SQLite database.

    Maps from `regions`:

        osm_id, wikidata, iso3166_2, name, aliases, neighbors

    where `aliases` and `neighbors` are ';'-separated lists.
    """
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT
                osm_id,
                wikidata,
                iso3166_2,
                name,
                aliases,
                neighbors
            FROM regions
            ORDER BY name ASC
            """
        ).fetchall()

        out: List[RegionEntry] = []
        for row in rows:
            data = {
                "osm_id": int(row["osm_id"]),
                "name": row["name"],
                "wikidata": row["wikidata"],
                "iso3166_2": row["iso3166_2"],
                "aliases": unpack_aliases(row["aliases"]),
                "neighbors": unpack_int_list(row["neighbors"]),
            }
            out.append(deserialize(data, RegionEntry))
        return out
    finally:
        conn.close()


# ------------------------------
# Group Loader (from DB)
# ------------------------------

def load_groups_from_db() -> List[GroupEntry]:
    """
    Load all GroupEntry objects from the SQLite database.

    Maps from `groups`:

        group_id, name, aliases, region_ids, neighbor_ids

    where `aliases`, `region_ids`, and `neighbor_ids` are ';'-separated lists.
    """
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT
                group_id,
                name,
                aliases,
                region_ids,
                neighbor_ids
            FROM groups
            ORDER BY group_id ASC
            """
        ).fetchall()

        out: List[GroupEntry] = []
        for row in rows:
            data = {
                "group_id": int(row["group_id"]),
                "name": row["name"],
                "aliases": unpack_aliases(row["aliases"]),
                "region_ids": unpack_int_list(row["region_ids"]),
                "neighbor_ids": unpack_int_list(row["neighbor_ids"]),
            }
            out.append(deserialize(data, GroupEntry))
        return out
    finally:
        conn.close()


# ------------------------------
# Direction Loader (from DB)
# ------------------------------
def load_directions_from_db(
    locale_by_cid: Optional[Dict[str, LocaleEntry]] = None,
) -> List[DirectionEntry]:
    """
    Load all DirectionEntry objects from the SQLite database.

    Maps from `directions`:

        dir_id, name, anchor_cid

    Direction aliases are inherited from the anchor locale.
    """
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT
                dir_id,
                name,
                anchor_cid
            FROM directions
            ORDER BY name ASC
            """
        ).fetchall()

        out: List[DirectionEntry] = []

        for row in rows:
            anchor_cid = str(row["anchor_cid"])
            anchor: Optional[LocaleEntry] = None
            aliases: List[str] = []

            if locale_by_cid is not None:
                anchor = locale_by_cid.get(anchor_cid)
                if anchor is not None:
                    # Inherit aliases from the anchor locale
                    aliases = list(anchor.aliases)

            data = {
                "dir_id": int(row["dir_id"]) if row["dir_id"] is not None else None,
                "name": row["name"],
                "anchor_cid": anchor_cid,
                "anchor": anchor,
                "aliases": aliases,
            }

            out.append(deserialize(data, DirectionEntry))

        return out
    finally:
        conn.close()

