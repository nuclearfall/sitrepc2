# src/sitrepc2/gazetteer/io.py
from __future__ import annotations

from typing import List, Dict, Optional, Iterable
from pathlib import Path
from sitrepc2.gazetteer.typedefs import (
    LocaleEntry,
    RegionEntry,
    GroupEntry,
    DirectionEntry,
)
import sqlite3
from sitrepc2.util.serialization import deserialize
from sitrepc2.config.paths import current_db_path
# ------------------------------
# Local DB connection helper
# ------------------------------

def connect() -> sqlite3.Connection:
    """
    Open a read-only connection to the authoritative records database.

    Gazetteer access is read-only and isolated from other persistence layers.
    """
    db_path = Path(current_db_path())

    if not db_path.exists():
        raise RuntimeError(
            f"Database not found at {db_path}. "
            "Run `sitrepc2 init` first."
        )

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con

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
            continue
    return out


# ------------------------------
# Locale Loader
# ------------------------------

def load_locales_from_db() -> List[LocaleEntry]:
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
                #"usage": int(row["usage"]) if row["usage"] not in (None, "") else 0,
            }
            out.append(deserialize(data, LocaleEntry))
        return out
    finally:
        conn.close()


# ------------------------------
# Region Loader
# ------------------------------

def load_regions_from_db() -> List[RegionEntry]:
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
# Group Loader
# ------------------------------

def load_groups_from_db() -> List[GroupEntry]:
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
# Direction Loader
# ------------------------------

def load_directions_from_db(
    locale_by_cid: Optional[Dict[str, LocaleEntry]] = None,
) -> List[DirectionEntry]:
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
            anchor = locale_by_cid.get(anchor_cid) if locale_by_cid else None
            aliases = list(anchor.aliases) if anchor else []

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


# ------------------------------
# Gazetteer aggregate loader (AUTHORITATIVE)
# ------------------------------

def load_gazetteer_from_db() -> tuple[
    List[LocaleEntry],
    List[RegionEntry],
    List[GroupEntry],
    List[DirectionEntry],
]:
    """
    Load the full gazetteer from the SQLite database.

    Returns:
        locales, regions, groups, directions

    This is the ONLY supported aggregate loader.
    """
    locales = load_locales_from_db()
    regions = load_regions_from_db()
    groups = load_groups_from_db()

    locale_by_cid = {l.cid: l for l in locales}
    directions = load_directions_from_db(locale_by_cid=locale_by_cid)

    return locales, regions, groups, directions
