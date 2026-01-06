from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Iterable

from sitrepc2.dom.dom_ingest import dom_ingest
from sitrepc2.dom.dom_dedupe import dom_dedupe
from sitrepc2.dom.dom_scoping import scope_dom_locations
from sitrepc2.dom.dom_tree_builder import build_dom_tree

from sitrepc2.lss.lss_scoping import LSSContextHint


# ============================================================
# Public API
# ============================================================

def build_dom_for_first_review(
    *,
    conn: sqlite3.Connection,
    ingest_post_id: int,
    lss_run_id: int,
    context_hints: Iterable[LSSContextHint],
) :
    """
    Build (or load) a DOM snapshot and return a hydrated DOM tree
    suitable for FIRST REVIEW (GUI / CLI).

    This function is:
      • idempotent
      • side-effect bounded
      • UI-safe
    """

    cur = conn.cursor()

    # --------------------------------------------------------
    # Check for existing CREATED snapshot
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT ds.id
        FROM dom_snapshot ds
        JOIN dom_post dp ON dp.id = ds.dom_post_id
        WHERE dp.ingest_post_id = ?
          AND dp.lss_run_id = ?
          AND ds.lifecycle_stage_id = 1
        """,
        (ingest_post_id, lss_run_id),
    )

    row = cur.fetchone()

    if row is not None:
        dom_snapshot_id = row[0]

        # Snapshot already exists → just hydrate
        return build_dom_tree(
            conn=conn,
            dom_snapshot_id=dom_snapshot_id,
        )

    # --------------------------------------------------------
    # No snapshot exists → create one
    # --------------------------------------------------------

    dom_snapshot_id = dom_ingest(
        conn=conn,
        ingest_post_id=ingest_post_id,
        lss_run_id=lss_run_id,
        created_at=datetime.utcnow(),
    )

    # --------------------------------------------------------
    # Structural dedupe (snapshot-scoped)
    # --------------------------------------------------------

    dom_dedupe(
        dom_conn=conn,
        context_hints=list(context_hints),
    )

    # --------------------------------------------------------
    # Gazetteer scoping (skip deduped nodes)
    # --------------------------------------------------------

    scope_dom_locations(
        dom_conn=conn,
        dom_snapshot_id=dom_snapshot_id,
        context_hints=context_hints,
    )

    # --------------------------------------------------------
    # Hydrate DOM tree for UI
    # --------------------------------------------------------

    return build_dom_tree(
        conn=conn,
        dom_snapshot_id=dom_snapshot_id,
    )
