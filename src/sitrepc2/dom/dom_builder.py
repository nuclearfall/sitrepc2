from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

import sqlite3

from sitrepc2.dom.nodes import (
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
# Helpers
# ============================================================

def _node_id(*parts: str) -> str:
    return "/".join(parts)


# ============================================================
# Phase A: Build immutable DOM skeleton from LSS
# ============================================================

def build_dom_skeleton(
    conn: sqlite3.Connection,
    *,
    ingest_post_id: int,
    lss_run_id: int,
) -> Dict[str, object]:
    """
    Build the immutable DOM structure from LSS tables.

    Returns:
        dict[node_id -> DomNode]
    """

    nodes: Dict[str, object] = {}

    # --------------------------------------------------------
    # Post
    # --------------------------------------------------------

    post_id = _node_id(f"post:{ingest_post_id}")
    post_node = PostNode(
        node_id=post_id,
        ingest_post_id=ingest_post_id,
        lss_run_id=lss_run_id,
        summary=f"Post {ingest_post_id}",
    )
    nodes[post_id] = post_node

    # --------------------------------------------------------
    # Sections
    # --------------------------------------------------------

    sections = conn.execute(
        """
        SELECT id, ordinal
        FROM lss_sections
        WHERE lss_run_id = ?
        ORDER BY ordinal
        """,
        (lss_run_id,),
    ).fetchall()

    section_nodes: Dict[int, SectionNode] = {}

    for sec in sections:
        sec_id = _node_id(post_id, f"sec:{sec['ordinal']}")
        sec_node = SectionNode(
            node_id=sec_id,
            section_index=sec["ordinal"],
            summary=f"Section {sec['ordinal']}",
        )
        post_node.add_child(sec_node)
        nodes[sec_id] = sec_node
        section_nodes[sec["id"]] = sec_node

    # --------------------------------------------------------
    # Events + Actors
    # --------------------------------------------------------

    rows = conn.execute(
        """
        SELECT
            e.id            AS event_id,
            e.section_id,
            e.ordinal       AS event_ordinal,
            e.event_uid,
            rc.text         AS actor_text
        FROM lss_events e
        LEFT JOIN lss_role_candidates rc
            ON rc.lss_event_id = e.id
           AND rc.role_kind = 'ACTOR'
        WHERE e.lss_run_id = ?
        ORDER BY e.section_id, e.ordinal
        """,
        (lss_run_id,),
    ).fetchall()

    events_by_id: Dict[int, EventNode] = {}

    for row in rows:
        sec_node = section_nodes.get(row["section_id"])
        if not sec_node:
            continue

        evt_id = _node_id(sec_node.node_id, f"evt:{row['event_ordinal']}")

        if evt_id not in nodes:
            evt_node = EventNode(
                node_id=evt_id,
                event_uid=row["event_uid"],
                summary=row["event_uid"],
            )
            sec_node.add_child(evt_node)
            nodes[evt_id] = evt_node
            events_by_id[row["event_id"]] = evt_node
        else:
            evt_node = nodes[evt_id]

        if row["actor_text"]:
            evt_node.actors.append(
                Actor(
                    text=row["actor_text"],
                    gazetteer_group_id=None,
                )
            )

    # --------------------------------------------------------
    # Location series + locations
    # --------------------------------------------------------

    rows = conn.execute(
        """
        SELECT
            e.id        AS event_id,
            s.id        AS series_id,
            li.ordinal  AS loc_ordinal,
            li.text     AS loc_text
        FROM lss_location_series s
        JOIN lss_events e
            ON e.id = s.lss_event_id
        JOIN lss_location_items li
            ON li.series_id = s.id
        WHERE e.lss_run_id = ?
        ORDER BY e.id, s.id, li.ordinal
        """,
        (lss_run_id,),
    ).fetchall()

    series_index: Dict[int, int] = defaultdict(int)
    series_nodes: Dict[int, LocationSeriesNode] = {}

    for row in rows:
        evt_node = events_by_id.get(row["event_id"])
        if not evt_node:
            continue

        if row["series_id"] not in series_nodes:
            idx = series_index[row["event_id"]]
            series_index[row["event_id"]] += 1

            ser_id = _node_id(evt_node.node_id, f"ser:{idx}")
            ser_node = LocationSeriesNode(
                node_id=ser_id,
                series_index=idx,
                summary="Location series",
            )
            evt_node.add_child(ser_node)
            nodes[ser_id] = ser_node
            series_nodes[row["series_id"]] = ser_node

        ser_node = series_nodes[row["series_id"]]

        loc_id = _node_id(ser_node.node_id, f"loc:{row['loc_ordinal']}")
        loc_node = LocationNode(
            node_id=loc_id,
            mention_text=row["loc_text"],
            summary=row["loc_text"],
            resolved=False,
        )
        ser_node.add_child(loc_node)
        nodes[loc_id] = loc_node

    return nodes
