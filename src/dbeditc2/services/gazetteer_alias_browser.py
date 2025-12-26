# src/dbeditc2/services/gazetteer_alias_browser.py
from __future__ import annotations

import sqlite3
from typing import Iterable

from sitrepc2.config.paths import gazetteer_path
from dbeditc2.enums import CollectionKind
from dbeditc2.models import EntrySummary


_TABLE_FOR_KIND = {
    CollectionKind.LOCATIONS: ("location_aliases", "location_id", "locations"),
    CollectionKind.REGIONS: ("region_aliases", "region_id", "regions"),
    CollectionKind.GROUPS: ("group_aliases", "group_id", "groups"),
    CollectionKind.DIRECTIONS: ("direction_aliases", "direction_id", "directions"),
}


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(gazetteer_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def list_aliases(
    *,
    kind: CollectionKind,
    search_text: str | None = None,
) -> list[EntrySummary]:
    """
    List aliases for a gazetteer entity type.

    - If search_text is None or empty: list ALL aliases
    - Otherwise: filter by normalized LIKE %text%

    FAILS LOUDLY if schema expectations are violated.
    """
    if kind not in _TABLE_FOR_KIND:
        raise ValueError(f"Alias listing not supported for {kind}")

    alias_table, id_col, entity_table = _TABLE_FOR_KIND[kind]

    params: list[str] = []
    where = ""

    if search_text:
        norm = " ".join(search_text.lower().split())
        where = "WHERE a.normalized LIKE ?"
        params.append(f"%{norm}%")

    sql = f"""
        SELECT
            a.alias,
            a.{id_col} AS entity_id,
            e.name AS canonical_name
        FROM {alias_table} a
        JOIN {entity_table} e
          ON e.{id_col} = a.{id_col}
        {where}
        ORDER BY a.alias
    """

    with _conn() as con:
        rows = con.execute(sql, params).fetchall()

    if rows is None:
        raise RuntimeError("Alias query failed unexpectedly")

    return [
        EntrySummary(
            entry_id=row["entity_id"],
            display_name=row["alias"],
            subtitle=row["canonical_name"],
            editable=False,
        )
        for row in rows
    ]
