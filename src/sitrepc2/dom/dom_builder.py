from __future__ import annotations

from collections import defaultdict
from typing import Dict

import sqlite3

from sitrepc2.dom.nodes import (
    PostNode,
    SectionNode,
    EventNode,
    LocationSeriesNode,
    LocationNode,
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

    DEDUPE RULE (CANONICAL):
    - Events are deduped by (section_id, start_token, end_token, text)
    - Labels are NOT part of identity
    - Actors are OPTIONAL metadata
    - Location series attach to the deduped event
    """

    nodes: Dict[str, object] = {}

    # --------------------------------------------------------
    # Post
    # --------------------------------------------------------

    post_node_id = _node_id(f"post:{ingest_post_id}")
    post_node = PostNode(
        node_id=post_node_id,
        ingest_post_id=ingest_post_id,
        lss_run_id=lss_run_id,
        summary=f"Post {ingest_post_id}",
    )
    nodes[post_node_id] = post_node

    # --------------------------------------------------------
    # Sections
    # --------------------------------------------------------

    section_rows = conn.execute(
        """
        SELECT id, ordinal
        FROM lss_sections
        WHERE lss_run_id = ?
        ORDER BY ordinal
        """,
        (lss_run_id,),
    ).fetchall()

    section_nodes: Dict[int, SectionNode] = {}

    for row in section_rows:
        sec_node_id = _node_id(post_node_id, f"sec:{row['ordinal']}")
        sec_node = SectionNode(
            node_id=sec_node_id,
            section_index=row["ordinal"],
            summary=f"Section {row['ordinal']}",
        )
        post_node.add_child(sec_node)
        nodes[sec_node_id] = sec_node
        section_nodes[row["id"]] = sec_node

    # --------------------------------------------------------
    # Events — FETCH + DEDUPE
    # --------------------------------------------------------

    event_rows = conn.execute(
        """
        SELECT
            id,
            section_id,
            ordinal,
            event_uid,
            label,
            start_token,
            end_token,
            text
        FROM lss_events
        WHERE lss_run_id = ?
        ORDER BY section_id, start_token, end_token, ordinal
        """,
        (lss_run_id,),
    ).fetchall()

    # Group by canonical equivalence key
    event_groups = defaultdict(list)

    for row in event_rows:
        key = (
            row["section_id"],
            row["start_token"],
            row["end_token"],
            row["text"],
        )
        event_groups[key].append(row)

    # Maps ANY lss_event.id → deduped EventNode
    events_by_db_id: Dict[int, EventNode] = {}

    for (section_id, _start, _end, _text), rows in event_groups.items():
        sec_node = section_nodes.get(section_id)
        if not sec_node:
            continue

        # Canonical representative = first row
        rep = rows[0]

        evt_node_id = _node_id(
            sec_node.node_id,
            f"evt:{rep['ordinal']}",
        )

        # Aggregate labels for display
        labels = sorted({r["label"] for r in rows if r["label"]})
        summary = ", ".join(labels) if labels else rep["event_uid"]

        evt_node = EventNode(
            node_id=evt_node_id,
            event_uid=rep["event_uid"],
            summary=summary,
        )

        sec_node.add_child(evt_node)
        nodes[evt_node_id] = evt_node

        # Map ALL source LSS events to this DOM node
        for r in rows:
            events_by_db_id[r["id"]] = evt_node

    # --------------------------------------------------------
    # Actors (OPTIONAL metadata)
    # --------------------------------------------------------

    actor_rows = conn.execute(
        """
        SELECT
            lss_event_id,
            text
        FROM lss_role_candidates
        WHERE role_kind = 'ACTOR'
        """
    ).fetchall()

    for row in actor_rows:
        evt_node = events_by_db_id.get(row["lss_event_id"])
        if not evt_node:
            continue

        evt_node.actors.append(
            Actor(
                text=row["text"],
                gazetteer_group_id=None,
            )
        )

    # --------------------------------------------------------
    # Location series + locations
    # --------------------------------------------------------

    loc_rows = conn.execute(
        """
        SELECT
            s.id        AS series_id,
            s.lss_event_id,
            li.ordinal  AS loc_ordinal,
            li.text     AS loc_text
        FROM lss_location_series s
        JOIN lss_location_items li
            ON li.series_id = s.id
        ORDER BY s.lss_event_id, s.id, li.ordinal
        """
    ).fetchall()

    series_nodes: Dict[int, LocationSeriesNode] = {}
    series_index_by_event: Dict[int, int] = defaultdict(int)

    for row in loc_rows:
        evt_node = events_by_db_id.get(row["lss_event_id"])
        if not evt_node:
            continue

        if row["series_id"] not in series_nodes:
            idx = series_index_by_event[id(evt_node)]
            series_index_by_event[id(evt_node)] += 1

            ser_node_id = _node_id(evt_node.node_id, f"ser:{idx}")
            ser_node = LocationSeriesNode(
                node_id=ser_node_id,
                series_index=idx,
                summary="Location series",
            )
            evt_node.add_child(ser_node)
            nodes[ser_node_id] = ser_node
            series_nodes[row["series_id"]] = ser_node

        ser_node = series_nodes[row["series_id"]]

        loc_node_id = _node_id(ser_node.node_id, f"loc:{row['loc_ordinal']}")
        loc_node = LocationNode(
            node_id=loc_node_id,
            mention_text=row["loc_text"],
            summary=row["loc_text"],
            resolved=False,
        )
        ser_node.add_child(loc_node)
        nodes[loc_node_id] = loc_node

    return nodes
