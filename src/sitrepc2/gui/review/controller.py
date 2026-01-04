from __future__ import annotations

from typing import Dict, Optional
from datetime import datetime

import sqlite3

from sitrepc2.dom.dom_builder import build_dom_skeleton
from sitrepc2.dom.nodes import BaseNode


# ============================================================================
# Review Controller
# ============================================================================

class ReviewController:
    """
    Controller for DOM review lifecycle and persistence.

    Owns:
    - dom_post
    - dom_snapshot
    - dom_node (immutable)
    - dom_node_state (snapshot-scoped)
    """

    INITIAL_REVIEW_STAGE_ID = 2

    def __init__(self, records_db_path: str) -> None:
        self.records_db_path = records_db_path

    # ------------------------------------------------------------------
    # Lifecycle entry
    # ------------------------------------------------------------------

    def enter_initial_review(
        self,
        *,
        ingest_post_id: int,
        lss_run_id: int,
    ) -> tuple[int, Dict[str, BaseNode]]:
        """
        Ensure INITIAL_REVIEW snapshot exists and DOM structure is materialized.

        Returns:
            (dom_snapshot_id, dom_nodes_by_node_id)
        """
        conn = sqlite3.connect(self.records_db_path)
        conn.row_factory = sqlite3.Row

        with conn:
            dom_post_id = self._ensure_dom_post(
                conn,
                ingest_post_id,
                lss_run_id,
            )

            dom_snapshot_id = self._ensure_snapshot(
                conn,
                dom_post_id,
            )

            dom_nodes = self._ensure_dom_nodes(
                conn,
                dom_post_id,
                dom_snapshot_id,
                ingest_post_id,
                lss_run_id,
            )

        conn.close()
        return dom_snapshot_id, dom_nodes

    # ------------------------------------------------------------------
    # dom_post / snapshot
    # ------------------------------------------------------------------

    def _ensure_dom_post(
        self,
        conn: sqlite3.Connection,
        ingest_post_id: int,
        lss_run_id: int,
    ) -> int:
        row = conn.execute(
            """
            SELECT id FROM dom_post
            WHERE ingest_post_id = ? AND lss_run_id = ?
            """,
            (ingest_post_id, lss_run_id),
        ).fetchone()

        if row:
            return row["id"]

        cur = conn.execute(
            """
            INSERT INTO dom_post (ingest_post_id, lss_run_id)
            VALUES (?, ?)
            """,
            (ingest_post_id, lss_run_id),
        )
        return cur.lastrowid

    def _ensure_snapshot(
        self,
        conn: sqlite3.Connection,
        dom_post_id: int,
    ) -> int:
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
    # DOM materialization
    # ------------------------------------------------------------------

    def _ensure_dom_nodes(
        self,
        conn: sqlite3.Connection,
        dom_post_id: int,
        dom_snapshot_id: int,
        ingest_post_id: int,
        lss_run_id: int,
    ) -> Dict[str, BaseNode]:
        """
        Build DOM skeleton from LSS and persist immutable structure.
        """
        nodes = build_dom_skeleton(
            conn,
            ingest_post_id=ingest_post_id,
            lss_run_id=lss_run_id,
        )

        for node in nodes.values():
            # dom_node (immutable)
            conn.execute(
                """
                INSERT OR IGNORE INTO dom_node (
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
                    node.node_type,
                    node.parent.node_id if node.parent else None,
                    node.sibling_order,
                ),
            )

            # dom_node_state (snapshot-scoped)
            conn.execute(
                """
                INSERT OR IGNORE INTO dom_node_state (
                    dom_snapshot_id,
                    dom_node_id,
                    selected,
                    summary
                )
                VALUES (?, ?, 1, ?)
                """,
                (
                    dom_snapshot_id,
                    node.node_id,
                    node.summary,
                ),
            )

        return nodes

    # ------------------------------------------------------------------
    # Selection updates
    # ------------------------------------------------------------------

    def set_node_selected(
        self,
        *,
        dom_snapshot_id: int,
        dom_node_id: str,
        selected: bool,
    ) -> None:
        conn = sqlite3.connect(self.records_db_path)
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

    def get_node_selection(
        self,
        *,
        dom_snapshot_id: int,
        dom_node_id: str,
    ) -> bool:
        conn = sqlite3.connect(self.records_db_path)
        row = conn.execute(
            """
            SELECT selected FROM dom_node_state
            WHERE dom_snapshot_id = ? AND dom_node_id = ?
            """,
            (dom_snapshot_id, dom_node_id),
        ).fetchone()
        conn.close()
        return bool(row["selected"]) if row else False
