# src/sitrepc2/dom/dom_enrichment.py
from __future__ import annotations

from typing import Dict, Iterable, List, Optional
from collections import defaultdict

import sqlite3

from sitrepc2.dom.nodes import (
    DomNode,
    PostNode,
    SectionNode,
    EventNode,
    LocationSeriesNode,
    LocationNode,
    LocationCandidateNode,
    Context,
)

# ============================================================
# Context utilities
# ============================================================

def effective_context(
    node: DomNode,
) -> Dict[str, Context]:
    """
    Compute effective context for a node by walking upward.

    Rules:
    - One context per ctx_kind
    - Lower node overrides higher node
    - Deselected context is ignored
    """

    out: Dict[str, Context] = {}
    cur: Optional[DomNode] = node

    while cur:
        for ctx in cur.contexts:
            if not ctx.selected:
                continue
            if ctx.ctx_kind not in out:
                out[ctx.ctx_kind] = ctx
        cur = cur.parent

    return out


# ============================================================
# Gazetteer lookup helpers
# ============================================================

def lookup_locations_by_alias(
    conn: sqlite3.Connection,
    *,
    text: str,
) -> List[int]:
    """
    Resolve mention text to candidate gazetteer.location_ids
    using alias table only.

    No context applied here.
    """

    rows = conn.execute(
        """
        SELECT DISTINCT location_id
        FROM aliases
        WHERE entity_type = 'LOCATION'
          AND normalized = lower(?)
        """,
        (text,),
    ).fetchall()

    return [r["location_id"] for r in rows]


def fetch_location_snapshot(
    conn: sqlite3.Connection,
    *,
    location_id: int,
) -> dict:
    """
    Fetch immutable snapshot of gazetteer.location row.
    """

    row = conn.execute(
        """
        SELECT
            location_id,
            lat,
            lon,
            name,
            place,
            wikidata
        FROM locations
        WHERE location_id = ?
        """,
        (location_id,),
    ).fetchone()

    return dict(row) if row else {}


# ============================================================
# Context-aware filtering
# ============================================================

def passes_region_constraint(
    conn: sqlite3.Connection,
    *,
    location_id: int,
    region_name: str,
) -> bool:
    """
    Conservative region filter:
    - TRUE if location is linked to region
    - FALSE otherwise
    """

    row = conn.execute(
        """
        SELECT 1
        FROM location_regions lr
        JOIN regions r
          ON r.region_id = lr.region_id
        WHERE lr.location_id = ?
          AND lower(r.name) = lower(?)
        """,
        (location_id, region_name),
    ).fetchone()

    return bool(row)


# ============================================================
# Candidate generation + attachment
# ============================================================

def enrich_locations(
    *,
    dom_nodes: Dict[str, DomNode],
    gazetteer_conn: sqlite3.Connection,
) -> None:
    """
    Enrich LocationNodes with LocationCandidateNodes.

    Contract:
    - No mutation of existing nodes
    - Candidates are attached as children
    - No resolution is performed
    """

    for node in dom_nodes.values():
        if not isinstance(node, LocationNode):
            continue

        # -----------------------------------------------
        # Phase 1: raw candidate IDs
        # -----------------------------------------------

        raw_ids = lookup_locations_by_alias(
            gazetteer_conn,
            text=node.mention_text,
        )

        # If nothing matches, create manual placeholder
        if not raw_ids:
            candidate = LocationCandidateNode(
                node_id=f"{node.node_id}/cand:manual",
                summary="Manual location",
                gazetteer_location_id=None,
                lat=None,
                lon=None,
                name=node.mention_text,
                place=None,
                wikidata=None,
                confidence=None,
                persists=False,
                dist_from_front=0.0,
            )
            node.add_child(candidate)
            continue

        # -----------------------------------------------
        # Phase 2: effective context
        # -----------------------------------------------

        ctx = effective_context(node)

        # -----------------------------------------------
        # Phase 3: apply conservative filters
        # -----------------------------------------------

        surviving_ids: List[int] = []

        for loc_id in raw_ids:
            ok = True

            if "REGION" in ctx:
                ok = passes_region_constraint(
                    gazetteer_conn,
                    location_id=loc_id,
                    region_name=ctx["REGION"].value,
                )

            if ok:
                surviving_ids.append(loc_id)

        # If filters remove everything, fall back to raw set
        if not surviving_ids:
            surviving_ids = raw_ids

        # -----------------------------------------------
        # Phase 4: snapshot + attach
        # -----------------------------------------------

        for idx, loc_id in enumerate(surviving_ids):
            snap = fetch_location_snapshot(
                gazetteer_conn,
                location_id=loc_id,
            )

            cand = LocationCandidateNode(
                node_id=f"{node.node_id}/cand:{idx}",
                summary=snap.get("name") or node.mention_text,
                gazetteer_location_id=loc_id,
                lat=snap.get("lat"),
                lon=snap.get("lon"),
                name=snap.get("name"),
                place=snap.get("place"),
                wikidata=snap.get("wikidata"),
                confidence=None,
                persists=False,
                dist_from_front=0.0,
            )

            node.add_child(cand)
