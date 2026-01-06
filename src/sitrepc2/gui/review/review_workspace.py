from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QWidget,
    QSplitter,
    QTableView,
    QPlainTextEdit,
    QTreeView,
    QLabel,
    QVBoxLayout,
    QHeaderView,
    QAbstractItemView,
    QPushButton,
)
from PySide6.QtCore import Qt, QModelIndex

from sitrepc2.config.paths import records_path

from sitrepc2.gui.review.lss_run_list_model import LssRunListModel
from sitrepc2.gui.review.dom_tree_model import DomTreeModel

from sitrepc2.dom.dom_first_review import build_dom_for_first_review
from sitrepc2.dom.dom_tree_builder import build_dom_tree
from sitrepc2.dom.dom_persist_tree import persist_dom_tree
from sitrepc2.dom.dom_snapshot import advance_dom_snapshot
from sitrepc2.dom.dom_commit_eligibility import recompute_commit_eligibility



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

        # ---- Review actions ----

        self.prepare_button = QPushButton("Prepare for Review")
        self.prepare_button.clicked.connect(self.prepare_for_review)

        self.commit_button = QPushButton("Commit Reviewed")
        self.commit_button.setEnabled(False)  # wired in Chunk 5
        self.commit_button.clicked.connect(self.commit_reviewed)


        action_panel = QWidget()
        action_layout = QVBoxLayout(action_panel)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.addWidget(self.prepare_button)
        action_layout.addWidget(self.commit_button)

        left_splitter.addWidget(action_panel)

        # ---- Run list ----

        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.verticalHeader().setVisible(False)

        left_splitter.addWidget(self.table_view)

        # ---- Text view ----

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        left_splitter.addWidget(self.text_edit)

        left_splitter.setStretchFactor(0, 0)  # buttons
        left_splitter.setStretchFactor(1, 2)  # run list
        left_splitter.setStretchFactor(2, 1)  # text

        # ====================
        # Right pane
        # ====================

        right_splitter = QSplitter(Qt.Vertical)

        self.dom_tree_view = QTreeView()
        self.dom_tree_view.setHeaderHidden(True)
        self.dom_tree_view.setExpandsOnDoubleClick(False)
        self.dom_tree_view.setItemsExpandable(True)

        right_splitter.addWidget(self.dom_tree_view)

        self.node_detail_placeholder = QWidget()
        self.node_detail_layout = QVBoxLayout(self.node_detail_placeholder)
        self.node_detail_label = QLabel("Select a DOM node to view details")
        self.node_detail_label.setAlignment(Qt.AlignCenter)
        self.node_detail_layout.addWidget(self.node_detail_label)

        right_splitter.addWidget(self.node_detail_placeholder)

        # ---- Assemble ----

        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_splitter)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)

        # ------------------------------------------------------------
        # Signals
        # ------------------------------------------------------------

        self.table_view.selectionModel().currentChanged.connect(
            self.on_run_selected
        )

        # ------------------------------------------------------------
        # Initial focus
        # ------------------------------------------------------------

        if self.model.rowCount() > 0:
            self.table_view.setCurrentIndex(self.model.index(0, 0))

    # ------------------------------------------------------------------
    # Run selection (focus only)
    # ------------------------------------------------------------------

    def on_run_selected(self, current: QModelIndex, previous: QModelIndex):
        if not current.isValid():
            return

        run = self.model.get_run(current)
        if not run:
            return

        run_id = run["id"]
        ingest_post_id = run["ingest_post_id"]

        # Reset DOM panel
        self.dom_tree_view.setModel(None)
        self.dom_model = None
        self.current_dom_tree = None
        self.dom_snapshot_id = None

        conn = sqlite3.connect(records_path())
        try:
            cur = conn.cursor()

            # ---- Load post text ----
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

            # ---- Load DOM snapshot if it exists ----
            snapshot_id = self._get_created_snapshot_id(
                conn,
                ingest_post_id,
                run_id,
            )
            self.commit_button.setEnabled(True)

            if snapshot_id is None:
                return

            self.current_dom_tree = build_dom_tree(
                conn=conn,
                dom_snapshot_id=snapshot_id,
            )
            self.dom_snapshot_id = snapshot_id

            self.dom_model = DomTreeModel(self.current_dom_tree)
            self.dom_tree_view.setModel(self.dom_model)
            self.dom_tree_view.expandAll()

        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Prepare for Review (batch)
    # ------------------------------------------------------------------

    def prepare_for_review(self):
        runs = self.model.get_checked_runs()
        if not runs:
            return

        conn = sqlite3.connect(records_path())
        try:
            for run in runs:
                lss_run_id = run["id"]
                ingest_post_id = run["ingest_post_id"]

                existing = self._get_created_snapshot_id(
                    conn,
                    ingest_post_id,
                    lss_run_id,
                )
                if existing is not None:
                    continue

                build_dom_for_first_review(
                    conn=conn,
                    ingest_post_id=ingest_post_id,
                    lss_run_id=lss_run_id,
                )

            self.model.clear_checks()

        finally:
            conn.close()


    def commit_reviewed(self):
        if not self.current_dom_tree or self.dom_snapshot_id is None:
            return

        conn = sqlite3.connect(records_path())
        try:
            # 1. Persist review edits
            persist_dom_tree(
                conn=conn,
                dom_snapshot_id=self.dom_snapshot_id,
                root=self.current_dom_tree,
            )

            # 2. Recompute eligibility on current snapshot
            recompute_commit_eligibility(
                conn=conn,
                dom_snapshot_id=self.dom_snapshot_id,
            )

            # 3. Advance lifecycle → new snapshot
            new_snapshot_id = advance_dom_snapshot(
                conn=conn,
                dom_snapshot_id=self.dom_snapshot_id,
            )

            # 4. Recompute eligibility on new snapshot
            recompute_commit_eligibility(
                conn=conn,
                dom_snapshot_id=new_snapshot_id,
            )

            # 5. Reload DOM tree
            self.current_dom_tree = build_dom_tree(
                conn=conn,
                dom_snapshot_id=new_snapshot_id,
            )
            self.dom_snapshot_id = new_snapshot_id

            self.dom_model = DomTreeModel(self.current_dom_tree)
            self.dom_tree_view.setModel(self.dom_model)
            self.dom_tree_view.expandAll()

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


