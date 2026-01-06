from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict, List


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

LIFECYCLE_STAGES = {
    1: "CREATED",
    2: "INITIAL_REVIEW",
    3: "PROCESSED",
    4: "FINAL_REVIEW",
    5: "AUDIT",
}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _ensure_lifecycle_stages(conn: sqlite3.Connection) -> None:
    """
    Ensure dom_lifecycle_stage contains the canonical stages.
    Idempotent.
    """
    cur = conn.cursor()

    for stage_id, name in LIFECYCLE_STAGES.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO dom_lifecycle_stage (id, name)
            VALUES (?, ?)
            """,
            (stage_id, name),
        )

    conn.commit()


def _fetchone_id(cur: sqlite3.Cursor) -> int:
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Expected row, got none")
    return row[0]


# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------

def dom_ingest(
    *,
    conn: sqlite3.Connection,
    ingest_post_id: int,
    lss_run_id: int,
    created_at: datetime,
) -> int:
    """
    Materialize DOM structure for (ingest_post_id, lss_run_id).

    Returns:
        dom_snapshot_id (CREATED stage)
    """

    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # ------------------------------------------------------------
    # Preconditions
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT ingest_post_id
        FROM lss_runs
        WHERE id = ?
        """,
        (lss_run_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"lss_run_id {lss_run_id} does not exist")

    if row[0] != ingest_post_id:
        raise ValueError(
            f"lss_run_id {lss_run_id} does not belong to ingest_post_id {ingest_post_id}"
        )

    cur.execute(
        """
        SELECT id
        FROM dom_post
        WHERE ingest_post_id = ? AND lss_run_id = ?
        """,
        (ingest_post_id, lss_run_id),
    )
    if cur.fetchone() is not None:
        raise RuntimeError(
            "DOM already ingested for this (ingest_post_id, lss_run_id)"
        )

    # ------------------------------------------------------------
    # Lifecycle stages
    # ------------------------------------------------------------

    _ensure_lifecycle_stages(conn)

    # ------------------------------------------------------------
    # dom_post
    # ------------------------------------------------------------

    cur.execute(
        """
        INSERT INTO dom_post (ingest_post_id, lss_run_id)
        VALUES (?, ?)
        """,
        (ingest_post_id, lss_run_id),
    )
    dom_post_id = cur.lastrowid

    # ------------------------------------------------------------
    # dom_snapshot (CREATED)
    # ------------------------------------------------------------

    cur.execute(
        """
        INSERT INTO dom_snapshot (
            dom_post_id,
            lifecycle_stage_id,
            created_at
        )
        VALUES (?, 1, ?)
        """,
        (dom_post_id, created_at.isoformat()),
    )
    dom_snapshot_id = cur.lastrowid

    # ------------------------------------------------------------
    # DOM POST node
    # ------------------------------------------------------------

    cur.execute(
        """
        INSERT INTO dom_node (
            dom_post_id,
            node_type,
            parent_id,
            sibling_order
        )
        VALUES (?, 'POST', NULL, 0)
        """,
        (dom_post_id,),
    )
    post_node_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO dom_node_provenance (dom_node_id)
        VALUES (?)
        """,
        (post_node_id,),
    )

    # ------------------------------------------------------------
    # Helper maps
    # ------------------------------------------------------------

    section_node_ids: Dict[int, int] = {}
    event_node_ids: Dict[int, int] = {}
    series_node_ids: Dict[int, int] = {}

    # ------------------------------------------------------------
    # Sections → DOM SECTION nodes
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT id, text, ordinal
        FROM lss_sections
        WHERE lss_run_id = ?
        ORDER BY ordinal
        """,
        (lss_run_id,),
    )

    for section_id, section_text, ordinal in cur.fetchall():
        cur.execute(
            """
            INSERT INTO dom_node (
                dom_post_id,
                node_type,
                parent_id,
                sibling_order
            )
            VALUES (?, 'SECTION', ?, ?)
            """,
            (dom_post_id, post_node_id, ordinal),
        )
        dom_section_id = cur.lastrowid
        section_node_ids[section_id] = dom_section_id

        cur.execute(
            """
            INSERT INTO dom_node_provenance (
                dom_node_id,
                lss_section_ids
            )
            VALUES (?, json_array(?))
            """,
            (dom_section_id, section_id),
        )

    # ------------------------------------------------------------
    # Events → DOM EVENT nodes
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT id, section_id, text, ordinal
        FROM lss_events
        WHERE lss_run_id = ?
        ORDER BY section_id, ordinal
        """,
        (lss_run_id,),
    )

    for event_id, section_id, event_text, ordinal in cur.fetchall():
        parent_id = (
            section_node_ids[section_id]
            if section_id is not None
            else post_node_id
        )

        cur.execute(
            """
            INSERT INTO dom_node (
                dom_post_id,
                node_type,
                parent_id,
                sibling_order
            )
            VALUES (?, 'EVENT', ?, ?)
            """,
            (dom_post_id, parent_id, ordinal),
        )
        dom_event_id = cur.lastrowid
        event_node_ids[event_id] = dom_event_id

        cur.execute(
            """
            INSERT INTO dom_node_provenance (
                dom_node_id,
                lss_event_id
            )
            VALUES (?, ?)
            """,
            (dom_event_id, event_id),
        )

    # ------------------------------------------------------------
    # Location series → DOM LOCATION_SERIES nodes
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT ls.id, ls.lss_event_id
        FROM lss_location_series ls
        JOIN lss_events e ON e.id = ls.lss_event_id
        WHERE e.lss_run_id = ?
        ORDER BY ls.id
        """,
        (lss_run_id,),
    )


    series_order: Dict[int, int] = {}

    for series_id, lss_event_id in cur.fetchall():
        parent_event_node = event_node_ids[lss_event_id]

        idx = series_order.get(lss_event_id, 0)
        series_order[lss_event_id] = idx + 1

        cur.execute(
            """
            INSERT INTO dom_node (
                dom_post_id,
                node_type,
                parent_id,
                sibling_order
            )
            VALUES (?, 'LOCATION_SERIES', ?, ?)
            """,
            (dom_post_id, parent_event_node, idx),
        )
        dom_series_id = cur.lastrowid
        series_node_ids[series_id] = dom_series_id

        cur.execute(
            """
            INSERT INTO dom_node_provenance (dom_node_id)
            VALUES (?)
            """,
            (dom_series_id,),
        )

    # ------------------------------------------------------------
    # Location items → DOM LOCATION nodes
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT id, series_id, text, ordinal
        FROM lss_location_items
        ORDER BY series_id, ordinal
        """
    )

    for item_id, series_id, loc_text, ordinal in cur.fetchall():
        parent_series_node = series_node_ids[series_id]

        cur.execute(
            """
            INSERT INTO dom_node (
                dom_post_id,
                node_type,
                parent_id,
                sibling_order
            )
            VALUES (?, 'LOCATION', ?, ?)
            """,
            (dom_post_id, parent_series_node, ordinal),
        )
        dom_location_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO dom_node_provenance (dom_node_id)
            VALUES (?)
            """,
            (dom_location_id,),
        )

    # ------------------------------------------------------------
    # Initialize dom_node_state for all nodes
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT id
        FROM dom_node
        WHERE dom_post_id = ?
        """,
        (dom_post_id,),
    )

    for (dom_node_id,) in cur.fetchall():
        cur.execute(
            """
            INSERT INTO dom_node_state (
                dom_snapshot_id,
                dom_node_id,
                selected,
                summary,
                resolved,
                resolution_source
            )
            VALUES (?, ?, TRUE, '', NULL, NULL)
            """,
            (dom_snapshot_id, dom_node_id),
        )

    conn.commit()
    return dom_snapshot_id
