from __future__ import annotations

import sqlite3
from typing import Dict, Optional

from nodes import (
    DomNode,
    PostNode,
    SectionNode,
    EventNode,
    LocationSeriesNode,
    LocationNode,
    LocationCandidateNode,
    Context,
    Actor,
)


# ============================================================
# SNAPSHOT RESOLUTION
# ============================================================

def resolve_snapshot_id(
    conn: sqlite3.Connection,
    dom_post_id: int,
    *,
    snapshot_id: Optional[int] = None,
    lifecycle_stage_id: Optional[int] = None,
) -> int:
    """
    Resolve exactly one snapshot to load.

    Caller must provide either snapshot_id or lifecycle_stage_id.
    """
    if snapshot_id is not None:
        return snapshot_id

    if lifecycle_stage_id is None:
        raise ValueError(
            "Either snapshot_id or lifecycle_stage_id must be provided"
        )

    row = conn.execute(
        """
        SELECT id
        FROM dom_snapshot
        WHERE dom_post_id = ?
          AND lifecycle_stage_id = ?
        """,
        (dom_post_id, lifecycle_stage_id),
    ).fetchone()

    if row is None:
        raise ValueError("No snapshot found for given lifecycle stage")

    return row[0]


# ============================================================
# STRUCTURE RECONSTRUCTION
# ============================================================

_NODE_CLASS_MAP = {
    "POST": PostNode,
    "SECTION": SectionNode,
    "EVENT": EventNode,
    "LOCATIONSERIES": LocationSeriesNode,
    "LOCATION": LocationNode,
    "LOCATIONCANDIDATE": LocationCandidateNode,
}


def load_structure(
    conn: sqlite3.Connection,
    dom_post_id: int,
) -> Dict[int, DomNode]:
    """
    Load immutable DOM structure and rebuild parent/child relationships.

    Returns a mapping of dom_node_id -> DomNode.
    """
    rows = conn.execute(
        """
        SELECT id, node_type, parent_id
        FROM dom_node
        WHERE dom_post_id = ?
        ORDER BY sibling_order
        """,
        (dom_post_id,),
    ).fetchall()

    nodes: Dict[int, DomNode] = {}

    # Pass 1: instantiate empty shells
    for node_id, node_type, _ in rows:
        cls = _NODE_CLASS_MAP[node_type]
        nodes[node_id] = cls(
            node_id=node_id,
            summary="",
        )

    # Pass 2: wire parent/children
    for node_id, _, parent_id in rows:
        if parent_id is not None:
            nodes[parent_id].add_child(nodes[node_id])

    return nodes


# ============================================================
# SNAPSHOT APPLICATION
# ============================================================

def apply_node_state(
    conn: sqlite3.Connection,
    snapshot_id: int,
    nodes: Dict[int, DomNode],
) -> None:
    rows = conn.execute(
        """
        SELECT dom_node_id, selected, summary, resolved
        FROM dom_node_state
        WHERE dom_snapshot_id = ?
        """,
        (snapshot_id,),
    ).fetchall()

    for node_id, selected, summary, resolved in rows:
        node = nodes[node_id]
        node.selected = bool(selected)
        node.summary = summary
        if hasattr(node, "resolved"):
            node.resolved = bool(resolved)


def apply_contexts(
    conn: sqlite3.Connection,
    snapshot_id: int,
    nodes: Dict[int, DomNode],
) -> None:
    rows = conn.execute(
        """
        SELECT dom_node_id, ctx_kind, ctx_value
        FROM dom_context
        WHERE dom_snapshot_id = ?
        """,
        (snapshot_id,),
    ).fetchall()

    for node_id, kind, value in rows:
        nodes[node_id].contexts.append(
            Context(
                ctx_kind=kind,
                value=value,
                selected=True,
            )
        )


def apply_actors(
    conn: sqlite3.Connection,
    snapshot_id: int,
    nodes: Dict[int, DomNode],
) -> None:
    rows = conn.execute(
        """
        SELECT event_node_id, actor_text, gazetteer_group_id, selected
        FROM dom_actor
        WHERE dom_snapshot_id = ?
        """,
        (snapshot_id,),
    ).fetchall()

    for node_id, text, gid, selected in rows:
        nodes[node_id].actors.append(
            Actor(
                text=text,
                gazetteer_group_id=gid,
                selected=bool(selected),
            )
        )


def apply_location_candidates(
    conn: sqlite3.Connection,
    snapshot_id: int,
    nodes: Dict[int, DomNode],
) -> None:
    rows = conn.execute(
        """
        SELECT
            location_node_id,
            gazetteer_location_id,
            lat,
            lon,
            name,
            place,
            wikidata,
            confidence,
            selected,
            persists
        FROM dom_location_candidate
        WHERE dom_snapshot_id = ?
        """,
        (snapshot_id,),
    ).fetchall()

    for (
        location_node_id,
        gid,
        lat,
        lon,
        name,
        place,
        wikidata,
        confidence,
        selected,
        persists,
    ) in rows:
        candidate = LocationCandidateNode(
            node_id=-1,  # leaf; structural ID not required
            summary=name or "",
            gazetteer_location_id=gid,
            lat=lat,
            lon=lon,
            name=name,
            place=place,
            wikidata=wikidata,
            confidence=confidence,
            persists=bool(persists),
            selected=bool(selected),
            neartest_loc=frontline(lat, lon)
        )
        nodes[location_node_id].add_child(candidate)


# ============================================================
# SINGLE ENTRY POINT
# ============================================================

def load_dom_tree(
    conn: sqlite3.Connection,
    dom_post_id: int,
    *,
    snapshot_id: Optional[int] = None,
    lifecycle_stage_id: Optional[int] = None,
) -> PostNode:
    """
    Load a fully reconstructed DOM tree for a given post and snapshot.
    """
    sid = resolve_snapshot_id(
        conn,
        dom_post_id,
        snapshot_id=snapshot_id,
        lifecycle_stage_id=lifecycle_stage_id,
    )

    nodes = load_structure(conn, dom_post_id)

    apply_node_state(conn, sid, nodes)
    apply_contexts(conn, sid, nodes)
    apply_actors(conn, sid, nodes)
    apply_location_candidates(conn, sid, nodes)

    # Root is the only node without a parent
    root = next(node for node in nodes.values() if node.parent is None)
    return root
