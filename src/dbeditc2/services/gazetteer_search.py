# src/dbeditc2/services/gazetteer_search.py
from __future__ import annotations

import sqlite3

from dbeditc2.enums import CollectionKind
from dbeditc2.models import EntrySummary
from sitrepc2.config.paths import gazetteer_path


# ---------------------------------------------------------------------
# Domain mapping (entity → alias table)
# ---------------------------------------------------------------------

_DOMAIN_FOR_COLLECTION: dict[CollectionKind, tuple[str, str]] = {
    CollectionKind.LOCATIONS: ("location_aliases", "location_id"),
    CollectionKind.REGIONS: ("region_aliases", "region_id"),
    CollectionKind.GROUPS: ("group_aliases", "group_id"),
    CollectionKind.DIRECTIONS: ("direction_aliases", "direction_id"),
}


# ---------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(gazetteer_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def search_entities(
    *,
    collection: CollectionKind,
    text: str,
) -> list[EntrySummary]:
    """
    Search gazetteer aliases for the given collection.

    Behavior:
    - Queries the appropriate *_aliases table
    - Matches against normalized alias text
    - Returns one EntrySummary per alias
    - entry_id is the canonical entity id (e.g. location_id)
    - display_name is the alias text itself

    FAILS LOUDLY if collection is unsupported.
    """
    mapping = _DOMAIN_FOR_COLLECTION.get(collection)
    if mapping is None:
        raise ValueError(
            f"search_entities() does not support collection: {collection}"
        )

    alias_table, id_col = mapping

    norm = _normalize(text)
    like = f"{norm}%"

    sql = f"""
        SELECT
            alias,
            {id_col} AS entity_id
        FROM {alias_table}
        WHERE normalized LIKE ?
        ORDER BY alias
    """

    with _conn() as con:
        rows = con.execute(sql, (like,)).fetchall()

    if rows is None:
        raise RuntimeError(
            f"Alias search failed unexpectedly for {collection}"
        )

    return [
        EntrySummary(
            entry_id=row["entity_id"],
            display_name=row["alias"],
            editable=False,
        )
        for row in rows
    ]
