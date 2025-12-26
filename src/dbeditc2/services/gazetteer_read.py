# src/dbeditc2/services/gazetteer_read.py
from __future__ import annotations

import sqlite3

from dbeditc2.enums import CollectionKind
from dbeditc2.models import GazetteerEntityViewModel
from sitrepc2.config.paths import gazetteer_path


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(gazetteer_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def load_entity(
    collection: CollectionKind,
    entity_id: int,
) -> GazetteerEntityViewModel:
    """
    Load a gazetteer entity and all related alias/group/region data.

    Entity identity is resolved FIRST, all semantic data is joined SECOND.
    """
    if collection != CollectionKind.LOCATIONS:
        raise NotImplementedError(
            "Only LOCATION entities are supported at this stage"
        )

    with _conn() as con:
        # --- core location ---
        loc = con.execute(
            """
            SELECT location_id, lat, lon, name, place, wikidata
            FROM locations
            WHERE location_id = ?
            """,
            (entity_id,),
        ).fetchone()

        if loc is None:
            raise KeyError(f"Location not found: {entity_id}")

        # --- aliases ---
        aliases = [
            r["alias"]
            for r in con.execute(
                """
                SELECT alias
                FROM location_aliases
                WHERE location_id = ?
                ORDER BY alias
                """,
                (entity_id,),
            )
        ]

        # --- regions ---
        regions = [
            r["name"]
            for r in con.execute(
                """
                SELECT r.name
                FROM location_regions lr
                JOIN regions r ON r.region_id = lr.region_id
                WHERE lr.location_id = ?
                ORDER BY r.name
                """,
                (entity_id,),
            )
        ]

        # --- groups ---
        groups = [
            g["name"]
            for g in con.execute(
                """
                SELECT g.name
                FROM location_groups lg
                JOIN groups g ON g.group_id = lg.group_id
                WHERE lg.location_id = ?
                ORDER BY g.name
                """,
                (entity_id,),
            )
        ]

    return GazetteerEntityViewModel(
        entity_id=loc["location_id"],
        name=loc["name"],
        latitude=loc["lat"],
        longitude=loc["lon"],
        place_type=loc["place"],
        wikidata_id=loc["wikidata"],
        aliases=aliases,
        regions=regions,
        groups=groups,
        is_read_only=True,  # editing controlled at higher level
    )
