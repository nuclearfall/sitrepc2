from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QWidget,
    QSplitter,
    QTableView,
    QPlainTextEdit,
    QTreeView,
    QVBoxLayout,
    QHeaderView,
    QAbstractItemView,
    QPushButton,
)
from PySide6.QtCore import Qt, QModelIndex

from sitrepc2.config.paths import records_path

from sitrepc2.dom.nodes import DomNode
from sitrepc2.gui.review.lss_run_list_model import LssRunListModel
from sitrepc2.gui.review.dom_tree_model import DomTreeModel
from sitrepc2.gui.review.dom_node_detail_panel import DomNodeDetailPanel

from sitrepc2.dom.dom_first_review import build_dom_for_first_review
from sitrepc2.dom.dom_tree_builder import build_dom_tree
from sitrepc2.dom.dom_persist_tree import persist_dom_tree
from sitrepc2.dom.dom_snapshot import advance_dom_snapshot
from sitrepc2.dom.dom_commit import recompute_commit_eligibility


# ============================================================================
# DOM Review Workspace
# ============================================================================
class DomReviewWorkspace(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # ------------------------------------------------------------
        # Models / state
        # ------------------------------------------------------------

        runs_data = self._load_runs()
        self.model = LssRunListModel(runs_data, parent=self)

        self.current_dom_tree = None
        self.dom_snapshot_id = None
        self.dom_model = None

        # ------------------------------------------------------------
        # Layout
        # ------------------------------------------------------------

        layout = QVBoxLayout(self)
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)

        # ====================
        # Left pane
        # ====================

        left_splitter = QSplitter(Qt.Vertical)

        self.prepare_button = QPushButton("Prepare for Review")
        self.prepare_button.clicked.connect(self.prepare_for_review)

        self.commit_button = QPushButton("Commit Reviewed")
        self.commit_button.setEnabled(False)
        self.commit_button.clicked.connect(self.commit_reviewed)

        action_panel = QWidget()
        action_layout = QVBoxLayout(action_panel)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.addWidget(self.prepare_button)
        action_layout.addWidget(self.commit_button)

        left_splitter.addWidget(action_panel)

        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.verticalHeader().setVisible(False)

        left_splitter.addWidget(self.table_view)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        left_splitter.addWidget(self.text_edit)

        left_splitter.setStretchFactor(0, 0)
        left_splitter.setStretchFactor(1, 2)
        left_splitter.setStretchFactor(2, 1)

        # ====================
        # Right pane
        # ====================

        right_splitter = QSplitter(Qt.Vertical)

        self.dom_tree_view = QTreeView()
        self.dom_tree_view.setHeaderHidden(True)
        self.dom_tree_view.setExpandsOnDoubleClick(False)
        right_splitter.addWidget(self.dom_tree_view)

        self.node_detail_panel = DomNodeDetailPanel(parent=self)

        right_splitter.addWidget(self.node_detail_panel)

        # ---- Assemble ----
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)

        # ------------------------------------------------------------
        # Signals
        # ------------------------------------------------------------

        self.table_view.selectionModel().currentChanged.connect(
            self.on_run_focused
        )

        # ------------------------------------------------------------
        # Initial focus
        # ------------------------------------------------------------

        if self.model.rowCount() > 0:
            self.table_view.setCurrentIndex(self.model.index(0, 0))

    # ------------------------------------------------------------------
    # Focused run → preview DOM tree if snapshot exists
    # ------------------------------------------------------------------

    def on_run_focused(self, current: QModelIndex, previous: QModelIndex):
        if not current.isValid():
            return

        run = self.model.get_run(current)
        if not run:
            return

        run_id = run["id"]
        ingest_post_id = run["ingest_post_id"]

        # Reset state
        self.dom_tree_view.setModel(None)
        self.node_detail_panel.clear()
        self.current_dom_tree = None
        self.dom_snapshot_id = None
        self.commit_button.setEnabled(False)

        conn = sqlite3.connect(records_path())
        try:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT ip.text
                FROM ingest_posts ip
                JOIN lss_runs lr ON lr.ingest_post_id = ip.id
                WHERE lr.id = ?
                """,
                (run_id,),
            )
            row = cur.fetchone()
            self.text_edit.setPlainText(row[0] if row else "")

            if not row:
                return

            snapshot_id = self._get_created_snapshot_id(
                conn, ingest_post_id, run_id
            )
            if snapshot_id is None:
                return

            self.current_dom_tree = build_dom_tree(
                conn=conn,
                dom_snapshot_id=snapshot_id,
            )
            self.dom_snapshot_id = snapshot_id
            self.commit_button.setEnabled(True)

            self.dom_model = DomTreeModel(self.current_dom_tree)
            self.dom_tree_view.setModel(self.dom_model)
            self.dom_tree_view.expandAll()

            # 🔑 CONNECT TREE SELECTION *AFTER* MODEL IS SET
            self.dom_tree_view.selectionModel().currentChanged.connect(
                self.on_dom_node_selected
            )

        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Tree node selection → detail panel
    # ------------------------------------------------------------------

    def on_dom_node_selected(self, current: QModelIndex, previous: QModelIndex):
        if not current.isValid():
            self.node_detail_panel.clear()
            return

        node = current.internalPointer()
        if not isinstance(node, DomNode):
            self.node_detail_panel.clear()
            return

        self.node_detail_panel.set_node(node)


    # ------------------------------------------------------------------
    # Prepare for Review
    # ------------------------------------------------------------------

    def prepare_for_review(self):
        sel = self.table_view.selectionModel()
        if not sel:
            return

        runs = [
            self.model.get_run(idx)
            for idx in sel.selectedRows()
            if self.model.get_run(idx)
        ]
        if not runs:
            return

        conn = sqlite3.connect(records_path())
        try:
            for run in runs:
                run_id = run["id"]
                ingest_post_id = run["ingest_post_id"]

                if self._get_created_snapshot_id(conn, ingest_post_id, run_id):
                    continue

                build_dom_for_first_review(
                    conn=conn,
                    ingest_post_id=ingest_post_id,
                    lss_run_id=run_id,
                )
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Commit reviewed snapshot
    # ------------------------------------------------------------------

    def commit_reviewed(self):
        if not self.current_dom_tree or self.dom_snapshot_id is None:
            return

        conn = sqlite3.connect(records_path())
        try:
            persist_dom_tree(
                conn=conn,
                dom_snapshot_id=self.dom_snapshot_id,
                root=self.current_dom_tree,
            )

            recompute_commit_eligibility(
                conn=conn,
                dom_snapshot_id=self.dom_snapshot_id,
            )

            new_snapshot_id = advance_dom_snapshot(
                conn=conn,
                dom_snapshot_id=self.dom_snapshot_id,
            )

            recompute_commit_eligibility(
                conn=conn,
                dom_snapshot_id=new_snapshot_id,
            )

            self.current_dom_tree = build_dom_tree(
                conn=conn,
                dom_snapshot_id=new_snapshot_id,
            )
            self.dom_snapshot_id = new_snapshot_id

            self.dom_model = DomTreeModel(self.current_dom_tree)
            self.dom_tree_view.setModel(self.dom_model)
            self.dom_tree_view.expandAll()

            self.node_detail_panel.clear()

        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_created_snapshot_id(
        self,
        conn: sqlite3.Connection,
        ingest_post_id: int,
        lss_run_id: int,
    ) -> int | None:
        cur = conn.cursor()
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
        return row[0] if row else None

    def _load_runs(self) -> list[dict]:
        conn = sqlite3.connect(records_path())
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    lr.id,
                    lr.ingest_post_id,
                    ip.source,
                    ip.publisher,
                    ip.published_at,
                    ip.fetched_at
                FROM lss_runs lr
                JOIN ingest_posts ip ON ip.id = lr.ingest_post_id
                ORDER BY ip.published_at DESC
                """
            )
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()
