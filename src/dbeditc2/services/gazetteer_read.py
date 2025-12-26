# src/dbeditc2/services/gazetteer_read.py
from __future__ import annotations

import sqlite3
from typing import Iterable

from sitrepc2.config.paths import gazetteer_path

from dbeditc2.enums import CollectionKind
from dbeditc2.models import EntrySummary, GazetteerEntityViewModel
from sitrepc2.gazetteer.alias_service import load_aliases_for_entities


# ---------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(gazetteer_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


# ---------------------------------------------------------------------
# Collection listing
# ---------------------------------------------------------------------

def list_entities(kind: CollectionKind) -> list[EntrySummary]:
    """
    List entities for the given gazetteer collection.

    Read-only. Minimal fields only.
    """
    table, id_col, name_col = _table_info(kind)

    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT {id_col} AS entity_id, {name_col} AS name
            FROM {table}
            ORDER BY name
            """
        ).fetchall()

    return [
        EntrySummary(
            entry_id=row["entity_id"],
            display_name=row["name"],
            editable=False,  # editability handled later
        )
        for row in rows
    ]


# ---------------------------------------------------------------------
# Entity detail loading
# ---------------------------------------------------------------------

def load_entity(kind: CollectionKind, entity_id: int) -> GazetteerEntityViewModel:
    """
    Load full read-only details for a single gazetteer entity.
    """
    if kind == CollectionKind.LOCATIONS:
        return _load_location(entity_id)
    if kind == CollectionKind.REGIONS:
        return _load_region(entity_id)
    if kind == CollectionKind.GROUPS:
        return _load_group(entity_id)
    if kind == CollectionKind.DIRECTIONS:
        return _load_direction(entity_id)

    raise ValueError(f"Unsupported collection kind: {kind}")


# ---------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------

def _load_location(location_id: int) -> GazetteerEntityViewModel:
    with _conn() as con:
        row = con.execute(
            """
            SELECT name, lat, lon, place, wikidata
            FROM locations
            WHERE location_id = ?
            """,
            (location_id,),
        ).fetchone()

        if row is None:
            raise KeyError(f"Location not found: {location_id}")

        regions = con.execute(
            """
            SELECT r.name
            FROM location_regions lr
            JOIN regions r ON r.region_id = lr.region_id
            WHERE lr.location_id = ?
            ORDER BY r.name
            """,
            (location_id,),
        ).fetchall()

        groups = con.execute(
            """
            SELECT g.name
            FROM location_groups lg
            JOIN groups g ON g.group_id = lg.group_id
            WHERE lg.location_id = ?
            ORDER BY g.name
            """,
            (location_id,),
        ).fetchall()

    aliases = load_aliases_for_entities(
        domain="LOCATION",
        entity_ids=[location_id],
    )

    return GazetteerEntityViewModel(
        title=row["name"],
        is_read_only=True,
        name=row["name"],
        latitude=row["lat"],
        longitude=row["lon"],
        place_type=row["place"],
        wikidata_id=row["wikidata"],
        aliases=aliases,
        regions=[r["name"] for r in regions],
        groups=[g["name"] for g in groups],
    )


# ---------------------------------------------------------------------
# Region
# ---------------------------------------------------------------------

def _load_region(region_id: int) -> GazetteerEntityViewModel:
    with _conn() as con:
        row = con.execute(
            """
            SELECT name, wikidata
            FROM regions
            WHERE region_id = ?
            """,
            (region_id,),
        ).fetchone()

        if row is None:
            raise KeyError(f"Region not found: {region_id}")

    aliases = load_aliases_for_entities(
        domain="REGION",
        entity_ids=[region_id],
    )

    return GazetteerEntityViewModel(
        title=row["name"],
        is_read_only=True,
        name=row["name"],
        wikidata_id=row["wikidata"],
        aliases=aliases,
        regions=[],
        groups=[],
    )


# ---------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------

def _load_group(group_id: int) -> GazetteerEntityViewModel:
    with _conn() as con:
        row = con.execute(
            """
            SELECT name
            FROM groups
            WHERE group_id = ?
            """,
            (group_id,),
        ).fetchone()

        if row is None:
            raise KeyError(f"Group not found: {group_id}")

    aliases = load_aliases_for_entities(
        domain="GROUP",
        entity_ids=[group_id],
    )

    return GazetteerEntityViewModel(
        title=row["name"],
        is_read_only=True,
        name=row["name"],
        aliases=aliases,
        regions=[],
        groups=[],
    )


# ---------------------------------------------------------------------
# Direction
# ---------------------------------------------------------------------

def _load_direction(direction_id: int) -> GazetteerEntityViewModel:
    with _conn() as con:
        row = con.execute(
            """
            SELECT name
            FROM directions
            WHERE direction_id = ?
            """,
            (direction_id,),
        ).fetchone()

        if row is None:
            raise KeyError(f"Direction not found: {direction_id}")

    aliases = load_aliases_for_entities(
        domain="DIRECTION",
        entity_ids=[direction_id],
    )

    return GazetteerEntityViewModel(
        title=row["name"],
        is_read_only=True,
        name=row["name"],
        aliases=aliases,
        regions=[],
        groups=[],
    )


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _table_info(kind: CollectionKind) -> tuple[str, str, str]:
    if kind == CollectionKind.LOCATIONS:
        return "locations", "location_id", "name"
    if kind == CollectionKind.REGIONS:
        return "regions", "region_id", "name"
    if kind == CollectionKind.GROUPS:
        return "groups", "group_id", "name"
    if kind == CollectionKind.DIRECTIONS:
        return "directions", "direction_id", "name"

    raise ValueError(f"Unsupported collection kind: {kind}")
