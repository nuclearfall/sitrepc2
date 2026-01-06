from __future__ import annotations

import sqlite3
from typing import Iterable

from sitrepc2.dom.nodes import (
    DomNode,
    PostNode,
    EventNode,
    LocationNode,
    LocationCandidateNode,
    Context,
    Actor,
)


# ============================================================
# Public API
# ============================================================

def persist_dom_tree(
    *,
    conn: sqlite3.Connection,
    dom_snapshot_id: int,
    root: PostNode,
) -> None:
    """
    Persist review-state changes from an in-memory DOM tree
    back into records.db for a single snapshot.

    Structural invariants:
      • dom_node rows are immutable
      • Only snapshot-scoped tables are updated
    """

    cur = conn.cursor()

    # --------------------------------------------------------
    # Walk tree
    # --------------------------------------------------------

    def walk(node: DomNode):
        yield node
        for child in node.children:
            yield from walk(child)

    for node in walk(root):
        dom_node_id = int(node.node_id)

        # ----------------------------------------------------
        # dom_node_state
        # ----------------------------------------------------

        cur.execute(
            """
            UPDATE dom_node_state
            SET selected = ?,
                resolved = ?,
        +       summary = ?
            WHERE dom_snapshot_id = ?
              AND dom_node_id = ?
            """,
            (
                bool(node.selected),
                bool(getattr(node, "resolved", None)),
        +       node.summary,
                dom_snapshot_id,
                dom_node_id,
            ),
        )

        # ----------------------------------------------------
        # Context overrides
        # ----------------------------------------------------

        for ctx in getattr(node, "contexts", []):
            cur.execute(
                """
                UPDATE dom_context
                SET overridden = ?
                WHERE dom_snapshot_id = ?
                  AND dom_node_id = ?
                  AND ctx_kind = ?
                  AND ctx_value = ?
                """,
                (
                    not ctx.selected,
                    dom_snapshot_id,
                    dom_node_id,
                    ctx.ctx_kind,
                    ctx.value,
                ),
            )

        # ----------------------------------------------------
        # Actors (EVENT only)
        # ----------------------------------------------------

        if isinstance(node, EventNode):
            for actor in node.actors:
                cur.execute(
                    """
                    UPDATE dom_actor
                    SET selected = ?
                    WHERE dom_snapshot_id = ?
                      AND event_node_id = ?
                      AND actor_text = ?
                    """,
                    (
                        bool(actor.selected),
                        dom_snapshot_id,
                        dom_node_id,
                        actor.text,
                    ),
                )

        # ----------------------------------------------------
        # Location candidates
        # ----------------------------------------------------

        if isinstance(node, LocationNode):
            for child in node.children:
                if not isinstance(child, LocationCandidateNode):
                    continue

                cur.execute(
                    """
                    UPDATE dom_location_candidate
                    SET selected = ?,
                        confidence = ?,
                        persists = ?,
                        dist_from_front = ?
                    WHERE dom_snapshot_id = ?
                      AND location_node_id = ?
                      AND gazetteer_location_id = ?
                    """,
                    (
                        bool(child.selected),
                        child.confidence,
                        bool(child.persists),
                        child.dist_from_front,
                        dom_snapshot_id,
                        dom_node_id,
                        child.gazetteer_location_id,
                    ),
                )

    conn.commit()
