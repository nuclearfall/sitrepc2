from __future__ import annotations

import sqlite3
from typing import Optional

from nodes import (
    DomNode,
    PostNode,
    EventNode,
    LocationNode,
    LocationCandidateNode,
)


# ============================================================
# STRUCTURE PERSISTENCE (WRITE ONCE)
# ============================================================

def persist_structure_once(
    conn: sqlite3.Connection,
    post: PostNode,
) -> int:
    """
    Persist DOM structure exactly once.

    Writes:
    - dom_post
    - dom_node

    Returns dom_post_id.
    """
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO dom_post (ingest_post_id, lss_run_id)
        VALUES (?, ?)
        """,
        (post.ingest_post_id, post.lss_run_id),
    )
    dom_post_id = cur.lastrowid

    def walk(node: DomNode):
        cur.execute(
            """
            INSERT INTO dom_node (
                id,
                dom_post_id,
                node_type,
                parent_id,
                sibling_order
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                node.node_id,
                dom_post_id,
                node.__class__.__name__.replace("Node", "").upper(),
                node.parent.node_id if node.parent else None,
                node.parent.children.index(node) if node.parent else 0,
            ),
        )

        for child in node.children:
            walk(child)

    walk(post)
    conn.commit()
    return dom_post_id


# ============================================================
# SNAPSHOT CREATION
# ============================================================

def create_snapshot(
    conn: sqlite3.Connection,
    dom_post_id: int,
    lifecycle_stage_id: int,
) -> int:
    """
    Append a new snapshot for a lifecycle stage.
    Enforced as one-per-stage by schema.
    """
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO dom_snapshot (
            dom_post_id,
            lifecycle_stage_id,
            created_at
        )
        VALUES (?, ?, CURRENT_TIMESTAMP)
        """,
        (dom_post_id, lifecycle_stage_id),
    )
    conn.commit()
    return cur.lastrowid


# ============================================================
# SNAPSHOT STATE WRITERS
# ============================================================

def persist_node_state(
    conn: sqlite3.Connection,
    snapshot_id: int,
    node: DomNode,
) -> None:
    conn.execute(
        """
        INSERT INTO dom_node_state (
            dom_snapshot_id,
            dom_node_id,
            selected,
            summary,
            resolved,
            resolution_source
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            node.node_id,
            node.selected,
            node.summary,
            getattr(node, "resolved", None),
            None,
        ),
    )


def persist_contexts(
    conn: sqlite3.Connection,
    snapshot_id: int,
    node: DomNode,
) -> None:
    for ctx in node.contexts:
        conn.execute(
            """
            INSERT INTO dom_context (
                dom_snapshot_id,
                dom_node_id,
                ctx_kind,
                ctx_value,
                overridden
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                node.node_id,
                ctx.ctx_kind,
                ctx.value,
                False,
            ),
        )


def persist_actors(
    conn: sqlite3.Connection,
    snapshot_id: int,
    event: EventNode,
) -> None:
    for actor in event.actors:
        conn.execute(
            """
            INSERT INTO dom_actor (
                dom_snapshot_id,
                event_node_id,
                actor_text,
                gazetteer_group_id,
                selected
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                event.node_id,
                actor.text,
                actor.gazetteer_group_id,
                actor.selected,
            ),
        )


def persist_location_candidates(
    conn: sqlite3.Connection,
    snapshot_id: int,
    location: LocationNode,
) -> None:
    for child in location.children:
        if not isinstance(child, LocationCandidateNode):
            continue

        conn.execute(
            """
            INSERT INTO dom_location_candidate (
                dom_snapshot_id,
                location_node_id,
                gazetteer_location_id,
                lat,
                lon,
                name,
                place,
                wikidata,
                confidence,
                dist_from_front,
                selected,
                persists
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                location.node_id,
                child.gazetteer_location_id,
                child.lat,
                child.lon,
                child.name,
                child.place,
                child.wikidata,
                child.confidence,
                child.dist_from_front,
                child.selected,
                child.persists,
            ),
        )


# ============================================================
# SINGLE ENTRY POINT — SNAPSHOT PERSIST
# ============================================================

def persist_snapshot(
    conn: sqlite3.Connection,
    dom_post_id: int,
    lifecycle_stage_id: int,
    post: PostNode,
) -> int:
    """
    Persist a full DOM snapshot for a given lifecycle stage.
    """
    snapshot_id = create_snapshot(conn, dom_post_id, lifecycle_stage_id)

    def walk(node: DomNode):
        persist_node_state(conn, snapshot_id, node)
        persist_contexts(conn, snapshot_id, node)

        if isinstance(node, EventNode):
            persist_actors(conn, snapshot_id, node)

        if isinstance(node, LocationNode):
            persist_location_candidates(conn, snapshot_id, node)

        for child in node.children:
            walk(child)

    walk(post)
    conn.commit()
    return snapshot_id
