# src/sitrepc2/dom/dom_location_enrich.py

from __future__ import annotations

from typing import Dict, Iterable, Optional

import sqlite3

from sitrepc2.dom.nodes import (
    DomNode,
    LocationNode,
    LocationCandidateNode,
    Context,
)


# ============================================================
# Helpers
# ============================================================

def _iter_location_nodes(nodes: Dict[str, DomNode]) -> Iterable[LocationNode]:
    for node in nodes.values():
        if isinstance(node, LocationNode):
            yield node


def _effective_context(
    node: DomNode,
    *,
    ctx_kind: str,
) -> Optional[str]:
    """
    Walk upward to find the closest selected context of the given kind.
    """
    cur: Optional[DomNode] = node
    while cur:
        for ctx in cur.contexts:
            if ctx.ctx_kind == ctx_kind and ctx.selected:
                return ctx.value
        cur = cur.parent
    return None


def _lookup_gazetteer_candidates(
    *,
    conn: sqlite3.Connection,
    name: str,
    region: Optional[str],
) -> list[sqlite3.Row]:
    """
    Gazetteer lookup filtered by region if provided.
    """
    if region:
        return conn.execute(
            """
            SELECT
                l.location_id,
                l.lat,
                l.lon,
                l.name,
                l.place,
                l.wikidata
            FROM locations l
            JOIN location_regions lr
                ON lr.location_id = l.location_id
            JOIN regions r
                ON r.region_id = lr.region_id
            WHERE
                r.name = ?
                AND (
                    l.name = ?
                    OR l.location_id IN (
                        SELECT location_id
                        FROM location_aliases
                        WHERE alias = ?
                    )
                )
            """,
            (region, name, name),
        ).fetchall()

    # No region constraint
    return conn.execute(
        """
        SELECT
            l.location_id,
            l.lat,
            l.lon,
            l.name,
            l.place,
            l.wikidata
        FROM locations l
        WHERE
            l.name = ?
            OR l.location_id IN (
                SELECT location_id
                FROM location_aliases
                WHERE alias = ?
            )
        """,
        (name, name),
    ).fetchall()


# ============================================================
# Public API
# ============================================================

def enrich_locations_with_gazetteer(
    *,
    conn: sqlite3.Connection,
    nodes: Dict[str, DomNode],
) -> None:
    """
    Populate LocationNode.candidates using gazetteer matches,
    filtered by REGION context.

    Contract:
    - No inference
    - No auto-resolution
    - Context is REQUIRED to restrict, never to expand
    - One candidate node per gazetteer row
    """

    for loc in _iter_location_nodes(nodes):
        mention = loc.mention_text.strip()
        if not mention:
            continue

        region = _effective_context(loc, ctx_kind="REGION")

        rows = _lookup_gazetteer_candidates(
            conn=conn,
            name=mention,
            region=region,
        )

        for idx, row in enumerate(rows):
            cand_id = f"{loc.node_id}/cand:{idx}"

            cand = LocationCandidateNode(
                node_id=cand_id,
                summary=row["name"] or mention,

                gazetteer_location_id=row["location_id"],

                lat=row["lat"],
                lon=row["lon"],
                name=row["name"],
                place=row["place"],
                wikidata=row["wikidata"],

                confidence=None,
                persists=False,
                dist_from_front=0.0,
            )

            loc.add_child(cand)
            nodes[cand_id] = cand
