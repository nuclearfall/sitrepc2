# src/sitrepc2/gazetteer/alias_service.py
from __future__ import annotations

import sqlite3
from typing import Iterable, List, Sequence

from sitrepc2.config.paths import gazetteer_path


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def normalize_alias(text: str) -> str:
    return " ".join(text.lower().split())


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(gazetteer_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def search_entities_by_alias(
    *,
    domain: str,
    search_text: str,
) -> list[dict]:
    """
    Search canonical entities by alias substring.
    """
    norm = normalize_alias(search_text)
    like = f"{norm}%"

    table, id_col = _table_for_domain(domain)

    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT
                a.entity_id,
                e.name AS canonical_name
            FROM aliases a
            JOIN {table} e
              ON e.{id_col} = a.entity_id
            WHERE a.entity_type = ?
              AND a.normalized LIKE ?
            GROUP BY a.entity_id, canonical_name
            ORDER BY canonical_name
            """,
            (domain, like),
        ).fetchall()

    return [dict(r) for r in rows]


def load_aliases_for_entities(
    *,
    domain: str,
    entity_ids: Sequence[int | str],
) -> list[str]:
    if not entity_ids:
        return []

    placeholders = ",".join("?" for _ in entity_ids)

    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT DISTINCT normalized
            FROM aliases
            WHERE entity_type = ?
              AND entity_id IN ({placeholders})
            ORDER BY normalized
            """,
            (domain, *entity_ids),
        ).fetchall()

    return [r["normalized"] for r in rows]


def apply_alias_changes(
    *,
    domain: str,
    entity_ids: Sequence[int | str],
    added: Iterable[str],
    removed: Iterable[str],
) -> None:
    with _conn() as con:
        for entity_id in entity_ids:
            for alias in added:
                norm = normalize_alias(alias)
                con.execute(
                    """
                    INSERT OR IGNORE INTO aliases
                        (entity_type, entity_id, alias, normalized)
                    VALUES (?, ?, ?, ?)
                    """,
                    (domain, entity_id, alias, norm),
                )

            for alias in removed:
                norm = normalize_alias(alias)
                con.execute(
                    """
                    DELETE FROM aliases
                    WHERE entity_type = ?
                      AND entity_id = ?
                      AND normalized = ?
                    """,
                    (domain, entity_id, norm),
                )


# ---------------------------------------------------------------------
# Domain mapping
# ---------------------------------------------------------------------

def _table_for_domain(domain: str) -> tuple[str, str]:
    if domain == "LOCATION":
        return "locations", "location_id"
    if domain == "REGION":
        return "regions", "region_id"
    if domain == "GROUP":
        return "groups", "group_id"
    if domain == "DIRECTION":
        return "directions", "direction_id"
    raise ValueError(f"Unknown domain: {domain}")
