from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from sitrepc2.config.paths import records_path
from sitrepc2.dom.dom_ingest import dom_ingest


# ============================================================================
# Review Controller (DOM-backed, authoritative)
# ============================================================================

class ReviewController:
    """
    Controller for DOM-backed review.

    Authoritative sources:
    - lss_runs        (what exists)
    - dom_* tables    (what is reviewed)
    """

    INITIAL_REVIEW_STAGE_ID = 2

    def __init__(self) -> None:
        self.db_path = records_path()

    # ------------------------------------------------------------------
    # Reviewable runs
    # ------------------------------------------------------------------

    def list_reviewable_runs(self) -> List[dict]:
        """
        LSS runs that either:
        - have no DOM yet
        - OR have no INITIAL_REVIEW snapshot
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                r.id              AS lss_run_id,
                r.ingest_post_id,
                r.started_at,
                r.completed_at,
                COUNT(e.id)       AS event_count
            FROM lss_runs r
            LEFT JOIN lss_events e
                ON e.lss_run_id = r.id
            LEFT JOIN dom_post dp
                ON dp.ingest_post_id = r.ingest_post_id
               AND dp.lss_run_id     = r.id
            LEFT JOIN dom_snapshot ds
                ON ds.dom_post_id = dp.id
               AND ds.lifecycle_stage_id = ?
            WHERE ds.id IS NULL
            GROUP BY r.id
            ORDER BY r.started_at DESC, r.id DESC
            """,
            (self.INITIAL_REVIEW_STAGE_ID,),
        ).fetchall()

        conn.close()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Snapshot entry
    # ------------------------------------------------------------------

    def enter_initial_review(
        self,
        *,
        ingest_post_id: int,
        lss_run_id: int,
    ) -> int:
        """
        Ensure DOM exists and INITIAL_REVIEW snapshot exists.

        Returns:
            dom_snapshot_id
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        with conn:
            # dom_post
            row = conn.execute(
                """
                SELECT id FROM dom_post
                WHERE ingest_post_id = ? AND lss_run_id = ?
                """,
                (ingest_post_id, lss_run_id),
            ).fetchone()

            if row is None:
                # No DOM yet → ingest
                dom_ingest(
                    conn=conn,
                    ingest_post_id=ingest_post_id,
                    lss_run_id=lss_run_id,
                    created_at=datetime.utcnow(),
                )

                row = conn.execute(
                    """
                    SELECT id FROM dom_post
                    WHERE ingest_post_id = ? AND lss_run_id = ?
                    """,
                    (ingest_post_id, lss_run_id),
                ).fetchone()

            dom_post_id = row["id"]

            # snapshot
            row = conn.execute(
                """
                SELECT id FROM dom_snapshot
                WHERE dom_post_id = ? AND lifecycle_stage_id = ?
                """,
                (dom_post_id, self.INITIAL_REVIEW_STAGE_ID),
            ).fetchone()

            if row:
                return row["id"]

            cur = conn.execute(
                """
                INSERT INTO dom_snapshot (
                    dom_post_id,
                    lifecycle_stage_id,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    dom_post_id,
                    self.INITIAL_REVIEW_STAGE_ID,
                    datetime.utcnow().isoformat(),
                ),
            )
            return cur.lastrowid

    # ------------------------------------------------------------------
    # DOM tree loading
    # ------------------------------------------------------------------

    def load_dom_tree(
        self,
        *,
        dom_snapshot_id: int,
    ) -> List[dict]:
        """
        Returns DOM nodes with state, ordered for tree reconstruction.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                n.id            AS node_id,
                n.parent_id,
                n.node_type,
                n.sibling_order,
                s.selected,
                s.summary
            FROM dom_node n
            JOIN dom_node_state s
              ON s.dom_node_id = n.id
            WHERE s.dom_snapshot_id = ?
            ORDER BY n.parent_id, n.sibling_order
            """,
            (dom_snapshot_id,),
        ).fetchall()

        conn.close()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def set_node_selected(
        self,
        *,
        dom_snapshot_id: int,
        dom_node_id: int,
        selected: bool,
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute(
                """
                UPDATE dom_node_state
                SET selected = ?
                WHERE dom_snapshot_id = ? AND dom_node_id = ?
                """,
                (int(selected), dom_snapshot_id, dom_node_id),
            )
        conn.close()
