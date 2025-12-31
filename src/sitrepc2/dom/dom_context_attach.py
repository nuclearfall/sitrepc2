# src/sitrepc2/dom/dom_context_attach.py
from __future__ import annotations

from collections import defaultdict
from typing import Dict

import sqlite3

from sitrepc2.dom.nodes import (
    DomNode,
    PostNode,
    SectionNode,
    EventNode,
    LocationSeriesNode,
    LocationNode,
    Context,
)


# ============================================================
# Helpers
# ============================================================

def _index_nodes_by_type(nodes: Dict[str, DomNode]):
    posts = []
    sections = {}
    events = {}
    series = {}
    locations = {}

    for node in nodes.values():
        if isinstance(node, PostNode):
            posts.append(node)

        elif isinstance(node, SectionNode):
            sections[node.section_index] = node

        elif isinstance(node, EventNode):
            # event ordinal is encoded in node_id suffix
            # post/sec/evt:{ordinal}
            ordinal = int(node.node_id.split("evt:")[-1])
            events[ordinal] = node

        elif isinstance(node, LocationSeriesNode):
            # post/sec/evt/ser:{idx}
            idx = int(node.node_id.split("ser:")[-1])
            series[(node.parent.node_id, idx)] = node

        elif isinstance(node, LocationNode):
            # post/sec/evt/ser/loc:{ordinal}
            ordinal = int(node.node_id.split("loc:")[-1])
            locations[(node.parent.node_id, ordinal)] = node

    return posts, sections, events, series, locations


def _attach_context(node: DomNode, ctx_kind: str, value: str):
    """
    Attach context if this node does not already have this kind.
    Lower layers are expected to override via ordering.
    """
    if any(c.ctx_kind == ctx_kind for c in node.contexts):
        return

    node.contexts.append(
        Context(
            ctx_kind=ctx_kind,
            value=value,
            selected=True,
        )
    )


# ============================================================
# Public API
# ============================================================

def attach_contexts(
    *,
    conn: sqlite3.Connection,
    nodes: Dict[str, DomNode],
    lss_run_id: int,
) -> None:
    """
    Attach LSS context hints to DOM nodes.

    Contract:
    - No inference
    - No filtering
    - No candidate creation
    - One context per kind per node
    - Lower-level context overrides by later attachment
    """

    posts, sections, events, series_nodes, location_nodes = _index_nodes_by_type(nodes)

    rows = conn.execute(
        """
        SELECT
            ctx_kind,
            text,
            scope,
            target_id
        FROM lss_context_hints
        WHERE lss_run_id = ?
          AND source IN ('GAZETTEER', 'SYNTHETIC')
        ORDER BY
            CASE scope
                WHEN 'POST' THEN 0
                WHEN 'SECTION' THEN 1
                WHEN 'EVENT' THEN 2
                WHEN 'SERIES' THEN 3
                WHEN 'LOCATION' THEN 4
            END
        """,
        (lss_run_id,),
    ).fetchall()

    for row in rows:
        ctx_kind = row["ctx_kind"]
        value = row["text"]
        scope = row["scope"]
        target = row["target_id"]

        if not value:
            continue

        # ---------------------------------------------
        # POST
        # ---------------------------------------------
        if scope == "POST":
            for post in posts:
                _attach_context(post, ctx_kind, value)

        # ---------------------------------------------
        # SECTION
        # ---------------------------------------------
        elif scope == "SECTION":
            sec = sections.get(target)
            if sec:
                _attach_context(sec, ctx_kind, value)

        # ---------------------------------------------
        # EVENT
        # ---------------------------------------------
        elif scope == "EVENT":
            evt = events.get(target)
            if evt:
                _attach_context(evt, ctx_kind, value)

        # ---------------------------------------------
        # SERIES
        # ---------------------------------------------
        elif scope == "SERIES":
            for (evt_id, idx), ser in series_nodes.items():
                if idx == target:
                    _attach_context(ser, ctx_kind, value)

        # ---------------------------------------------
        # LOCATION
        # ---------------------------------------------
        elif scope == "LOCATION":
            for (ser_id, ordinal), loc in location_nodes.items():
                if ordinal == target:
                    _attach_context(loc, ctx_kind, value)
