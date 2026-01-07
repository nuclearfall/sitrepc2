from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict
import json


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
        "SELECT ingest_post_id FROM lss_runs WHERE id = ?",
        (lss_run_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"lss_run_id {lss_run_id} does not exist")
    if row[0] != ingest_post_id:
        raise ValueError("lss_run_id does not belong to ingest_post_id")

    cur.execute(
        """
        SELECT id FROM dom_post
        WHERE ingest_post_id = ? AND lss_run_id = ?
        """,
        (ingest_post_id, lss_run_id),
    )
    if cur.fetchone() is not None:
        raise RuntimeError("DOM already ingested for this run")

    # ------------------------------------------------------------
    # Lifecycle stages
    # ------------------------------------------------------------

    _ensure_lifecycle_stages(conn)

    # ------------------------------------------------------------
    # dom_post
    # ------------------------------------------------------------

    cur.execute(
        "INSERT INTO dom_post (ingest_post_id, lss_run_id) VALUES (?, ?)",
        (ingest_post_id, lss_run_id),
    )
    dom_post_id = cur.lastrowid

    # ------------------------------------------------------------
    # dom_snapshot (CREATED)
    # ------------------------------------------------------------

    cur.execute(
        """
        INSERT INTO dom_snapshot (dom_post_id, lifecycle_stage_id, created_at)
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
        INSERT INTO dom_node (dom_post_id, node_type, parent_id, sibling_order)
        VALUES (?, 'POST', NULL, 0)
        """,
        (dom_post_id,),
    )
    post_node_id = cur.lastrowid

    cur.execute(
        "INSERT INTO dom_node_provenance (dom_node_id) VALUES (?)",
        (post_node_id,),
    )

    # ------------------------------------------------------------
    # Helper maps
    # ------------------------------------------------------------

    section_node_ids: Dict[int, int] = {}
    event_node_ids: Dict[int, int] = {}
    series_node_ids: Dict[int, int] = {}

    # ------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT id, ordinal FROM lss_sections
        WHERE lss_run_id = ?
        ORDER BY ordinal
        """,
        (lss_run_id,),
    )

    for section_id, ordinal in cur.fetchall():
        cur.execute(
            """
            INSERT INTO dom_node (dom_post_id, node_type, parent_id, sibling_order)
            VALUES (?, 'SECTION', ?, ?)
            """,
            (dom_post_id, post_node_id, ordinal),
        )
        dom_section_id = cur.lastrowid
        section_node_ids[section_id] = dom_section_id

        cur.execute(
            """
            INSERT INTO dom_node_provenance (dom_node_id, lss_section_ids)
            VALUES (?, json_array(?))
            """,
            (dom_section_id, section_id),
        )

    # ------------------------------------------------------------
    # Events
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT id, section_id, ordinal FROM lss_events
        WHERE lss_run_id = ?
        ORDER BY section_id, ordinal
        """,
        (lss_run_id,),
    )

    for event_id, section_id, ordinal in cur.fetchall():
        parent_id = (
            section_node_ids[section_id]
            if section_id is not None
            else post_node_id
        )

        cur.execute(
            """
            INSERT INTO dom_node (dom_post_id, node_type, parent_id, sibling_order)
            VALUES (?, 'EVENT', ?, ?)
            """,
            (dom_post_id, parent_id, ordinal),
        )
        dom_event_id = cur.lastrowid
        event_node_ids[event_id] = dom_event_id

        cur.execute(
            """
            INSERT INTO dom_node_provenance (dom_node_id, lss_event_id)
            VALUES (?, ?)
            """,
            (dom_event_id, event_id),
        )

    # ------------------------------------------------------------
    # Location series
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
            INSERT INTO dom_node (dom_post_id, node_type, parent_id, sibling_order)
            VALUES (?, 'LOCATION_SERIES', ?, ?)
            """,
            (dom_post_id, parent_event_node, idx),
        )
        series_node_ids[series_id] = cur.lastrowid

        cur.execute(
            "INSERT INTO dom_node_provenance (dom_node_id) VALUES (?)",
            (series_node_ids[series_id],),
        )

    # ------------------------------------------------------------
    # Location items
    # ------------------------------------------------------------

    cur.execute(
        """
        SELECT li.id, li.series_id, li.ordinal, li.text
        FROM lss_location_items li
        JOIN lss_location_series ls ON ls.id = li.series_id
        JOIN lss_events e ON e.id = ls.lss_event_id
        WHERE e.lss_run_id = ?
        ORDER BY li.series_id, li.ordinal
        """,
        (lss_run_id,),
    )

    location_item_text: Dict[int, str] = {}

    for item_id, series_id, ordinal, text in cur.fetchall():
        parent_series_node = series_node_ids[series_id]

        cur.execute(
            """
            INSERT INTO dom_node (dom_post_id, node_type, parent_id, sibling_order)
            VALUES (?, 'LOCATION', ?, ?)
            """,
            (dom_post_id, parent_series_node, ordinal),
        )
        dom_location_id = cur.lastrowid
        location_item_text[dom_location_id] = text

        cur.execute(
            "INSERT INTO dom_node_provenance (dom_node_id) VALUES (?)",
            (dom_location_id,),
        )

    # ------------------------------------------------------------
    # Load LSS text for summaries
    # ------------------------------------------------------------

    cur.execute(
        "SELECT id, text FROM lss_sections WHERE lss_run_id = ?",
        (lss_run_id,),
    )
    section_text = dict(cur.fetchall())

    cur.execute(
        "SELECT id, text FROM lss_events WHERE lss_run_id = ?",
        (lss_run_id,),
    )
    event_text = dict(cur.fetchall())

    # ------------------------------------------------------------
    # Initialize dom_node_state WITH summaries
    # ------------------------------------------------------------

    cur.execute(
        "SELECT id, node_type FROM dom_node WHERE dom_post_id = ?",
        (dom_post_id,),
    )

    for dom_node_id, node_type in cur.fetchall():
        summary = ""

        if node_type == "EVENT":
            cur.execute(
                """
                SELECT lss_event_id
                FROM dom_node_provenance
                WHERE dom_node_id = ?
                """,
                (dom_node_id,),
            )
            row = cur.fetchone()
            if row and row[0] in event_text:
                summary = event_text[row[0]]

        elif node_type == "SECTION":
            cur.execute(
                """
                SELECT lss_section_ids
                FROM dom_node_provenance
                WHERE dom_node_id = ?
                """,
                (dom_node_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                section_ids = json.loads(row[0])
                if section_ids and section_ids[0] in section_text:
                    summary = section_text[section_ids[0]]

        elif node_type == "LOCATION":
            summary = location_item_text.get(dom_node_id, "")

        elif node_type == "LOCATION_SERIES":
            cur.execute(
                "SELECT id FROM dom_node WHERE parent_id = ? ORDER BY sibling_order",
                (dom_node_id,),
            )
            texts = [
                location_item_text.get(cid, "")
                for (cid,) in cur.fetchall()
                if cid in location_item_text
            ]
            summary = ", ".join(texts)

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
            VALUES (?, ?, TRUE, ?, NULL, NULL)
            """,
            (dom_snapshot_id, dom_node_id, summary),
        )

    conn.commit()
    return dom_snapshot_id
