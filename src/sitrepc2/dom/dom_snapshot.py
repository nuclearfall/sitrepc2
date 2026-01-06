from __future__ import annotations

import sqlite3
from datetime import datetime


# Legal linear transitions
LIFECYCLE_ORDER = {
    1: 2,  # CREATED → INITIAL_REVIEW
    2: 3,  # INITIAL_REVIEW → PROCESSED
    3: 4,  # PROCESSED → FINAL_REVIEW
    4: 5,  # FINAL_REVIEW → AUDIT
}


SNAPSHOT_TABLES = [
    "dom_node_state",
    "dom_context",
    "dom_actor",
    "dom_location_candidate",
    "dom_commit_eligibility",
]


def advance_dom_snapshot(
    *,
    conn: sqlite3.Connection,
    dom_snapshot_id: int,
) -> int:
    """
    Advance DOM snapshot to the next lifecycle stage.

    Steps:
      1. Validate legal lifecycle transition
      2. Create new dom_snapshot
      3. Clone snapshot-scoped tables
      4. Freeze old snapshot
    """

    cur = conn.cursor()

    # --------------------------------------------------
    # Resolve current snapshot
    # --------------------------------------------------

    cur.execute(
        """
        SELECT dom_post_id, lifecycle_stage_id
        FROM dom_snapshot
        WHERE id = ?
        """,
        (dom_snapshot_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"dom_snapshot_id {dom_snapshot_id} not found")

    dom_post_id, stage_id = row

    if stage_id not in LIFECYCLE_ORDER:
        raise ValueError("Snapshot already at terminal lifecycle stage")

    next_stage = LIFECYCLE_ORDER[stage_id]

    # --------------------------------------------------
    # Create new snapshot
    # --------------------------------------------------

    cur.execute(
        """
        INSERT INTO dom_snapshot (
            dom_post_id,
            lifecycle_stage_id,
            created_at
        )
        VALUES (?, ?, ?)
        """,
        (dom_post_id, next_stage, datetime.utcnow().isoformat()),
    )
    new_snapshot_id = cur.lastrowid

    # --------------------------------------------------
    # Clone snapshot-scoped tables
    # --------------------------------------------------

    for table in SNAPSHOT_TABLES:
        cur.execute(
            f"""
            INSERT INTO {table}
            SELECT
                {new_snapshot_id},
                *
            FROM {table}
            WHERE dom_snapshot_id = ?
            """,
            (dom_snapshot_id,),
        )

    conn.commit()
    return new_snapshot_id
