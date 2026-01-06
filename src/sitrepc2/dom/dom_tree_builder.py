from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional

from sitrepc2.dom.nodes import (
    DomNode,
    PostNode,
    SectionNode,
    EventNode,
    LocationSeriesNode,
    LocationNode,
    LocationCandidateNode,
    Actor,
    Context,
)


# ============================================================
# Public API
# ============================================================

def build_dom_tree(
    *,
    conn: sqlite3.Connection,
    dom_snapshot_id: int,
) -> PostNode:
    """
    Hydrate a DOM tree for a given snapshot.

    Returns:
        PostNode (root)
    """

    cur = conn.cursor()

    # --------------------------------------------------------
    # Load all nodes (structure + state)
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT
            dn.id,
            dn.node_type,
            dn.parent_id,
            dn.sibling_order,

            st.selected,
            st.resolved,
            st.deduped,
            st.dedupe_target_id,

            dp.lss_event_id,
            dp.lss_section_ids,
            dp.gazetteer_entity_id
        FROM dom_node dn
        JOIN dom_node_state st
          ON st.dom_node_id = dn.id
         AND st.dom_snapshot_id = ?
        LEFT JOIN dom_node_provenance dp
          ON dp.dom_node_id = dn.id
        ORDER BY dn.parent_id, dn.sibling_order
        """,
        (dom_snapshot_id,),
    )

    rows = cur.fetchall()

    # --------------------------------------------------------
    # Instantiate nodes (no linkage yet)
    # --------------------------------------------------------

    nodes: Dict[int, DomNode] = {}

    for (
        node_id,
        node_type,
        parent_id,
        sibling_order,
        selected,
        resolved,
        deduped,
        dedupe_target_id,
        lss_event_id,
        lss_section_ids,
        gaz_entity_id,
    ) in rows:

        if node_type == "POST":
            node = PostNode(
                node_id=str(node_id),
                summary="",
                ingest_post_id=-1,
                lss_run_id=-1,
            )

        elif node_type == "SECTION":
            node = SectionNode(
                node_id=str(node_id),
                summary="",
                section_index=sibling_order,
            )

        elif node_type == "EVENT":
            node = EventNode(
                node_id=str(node_id),
                summary="",
                event_uid=str(lss_event_id),
            )

        elif node_type == "LOCATION_SERIES":
            node = LocationSeriesNode(
                node_id=str(node_id),
                summary="",
                series_index=sibling_order,
            )

        elif node_type == "LOCATION":
            node = LocationNode(
                node_id=str(node_id),
                summary="",
                mention_text="",
                resolved=bool(resolved),
            )

        elif node_type == "LOCATION_CANDIDATE":
            node = LocationCandidateNode(
                node_id=str(node_id),
                summary="",
                gazetteer_location_id=gaz_entity_id,
                lat=None,
                lon=None,
                name=None,
                place=None,
                wikidata=None,
                confidence=None,
                persists=False,
                dist_from_front=0.0,
            )

        else:
            raise ValueError(f"Unknown node_type: {node_type}")

        # snapshot-scoped state
        node.selected = bool(selected)
        node.deduped = bool(deduped)
        node.dedupe_target = None  # resolved later if needed

        nodes[node_id] = node

    # --------------------------------------------------------
    # Link parent/children
    # --------------------------------------------------------

    root: Optional[PostNode] = None

    for (
        node_id,
        _,
        parent_id,
        *_,
    ) in rows:

        node = nodes[node_id]

        if parent_id is None:
            root = node  # POST
        else:
            parent = nodes[parent_id]
            parent.add_child(node)

    assert root is not None
    assert isinstance(root, PostNode)

    # --------------------------------------------------------
    # Attach contexts
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT dom_node_id, ctx_kind, ctx_value, overridden
        FROM dom_context
        WHERE dom_snapshot_id = ?
        """,
        (dom_snapshot_id,),
    )

    for node_id, kind, value, overridden in cur.fetchall():
        nodes[node_id].contexts.append(
            Context(
                ctx_kind=kind,
                value=value,
                selected=not overridden,
            )
        )

    # --------------------------------------------------------
    # Attach actors
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT event_node_id, actor_text, gazetteer_group_id, selected
        FROM dom_actor
        WHERE dom_snapshot_id = ?
        """,
        (dom_snapshot_id,),
    )

    for event_id, text, group_id, selected in cur.fetchall():
        event = nodes[event_id]
        assert isinstance(event, EventNode)
        event.actors.append(
            Actor(
                text=text,
                gazetteer_group_id=group_id,
                selected=bool(selected),
            )
        )

    # --------------------------------------------------------
    # Attach location candidates
    # --------------------------------------------------------

    cur.execute(
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
            persists,
            dist_from_front,
            selected
        FROM dom_location_candidate
        WHERE dom_snapshot_id = ?
        """,
        (dom_snapshot_id,),
    )

    for (
        loc_node_id,
        gaz_id,
        lat,
        lon,
        name,
        place,
        wikidata,
        confidence,
        persists,
        dist,
        selected,
    ) in cur.fetchall():

        loc_node = nodes[loc_node_id]
        assert isinstance(loc_node, LocationNode)

        candidate = LocationCandidateNode(
            node_id=f"{loc_node_id}:{gaz_id}",
            summary="",
            gazetteer_location_id=gaz_id,
            lat=lat,
            lon=lon,
            name=name,
            place=place,
            wikidata=wikidata,
            confidence=confidence,
            persists=bool(persists),
            dist_from_front=dist or 0.0,
        )
        candidate.selected = bool(selected)

        loc_node.add_child(candidate)

    return root
