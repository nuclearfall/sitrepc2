from PySide6.QtWidgets import (
    QWidget, QSplitter, QTableView, QPlainTextEdit, QTreeView, QLabel,
    QVBoxLayout, QHeaderView, QAbstractItemView, QPushButton
)
from PySide6.QtCore import Qt, QModelIndex

import sqlite3
from sitrepc2.config.paths import records_path

from sitrepc2.gui.review.lss_run_model import LssRunModel
from sitrepc2.gui.review.dom_tree_model import DomTreeModel
from sitrepc2.dom.dom_first_review import build_dom_for_first_review
from sitrepc2.dom.dom_persist_tree import persist_dom_tree

class DomReviewWorkspace(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        runs_data = self._load_runs()
        self.model = LssRunModel(runs_data, parent=self)

        self.dom_model = None
        self.current_dom_tree = None
        self.dom_snapshot_id = None

        layout = QVBoxLayout(self)

        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)

        # --------------------
        # Left pane
        # --------------------

        left_splitter = QSplitter(Qt.Vertical)

        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.verticalHeader().setVisible(False)

        left_splitter.addWidget(self.table_view)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        left_splitter.addWidget(self.text_edit)

        left_splitter.setStretchFactor(0, 2)
        left_splitter.setStretchFactor(1, 1)

        # --------------------
        # Right pane
        # --------------------

        right_splitter = QSplitter(Qt.Vertical)

        self.dom_tree_view = QTreeView()
        self.dom_tree_view.setHeaderHidden(True)
        right_splitter.addWidget(self.dom_tree_view)

        self.node_detail_placeholder = QWidget()
        self.node_detail_layout = QVBoxLayout(self.node_detail_placeholder)

        self.node_detail_label = QLabel("Node details will appear here")
        self.node_detail_label.setAlignment(Qt.AlignCenter)
        self.node_detail_layout.addWidget(self.node_detail_label)

        self.save_button = QPushButton("Save Changes")
        self.save_button.clicked.connect(self.save_dom_tree)
        self.save_button.setEnabled(False)
        self.node_detail_layout.addWidget(self.save_button)

        right_splitter.addWidget(self.node_detail_placeholder)

        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_splitter)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)

        # --------------------
        # Signals
        # --------------------

        self.table_view.selectionModel().currentChanged.connect(self.on_run_selected)

        # --------------------
        # Initial selection
        # --------------------

        if self.model.rowCount() > 0:
            first_index = self.model.index(0, 0)
            self.table_view.setCurrentIndex(first_index)

    def on_run_selected(self, current_index: QModelIndex, previous_index: QModelIndex):
        if not current_index.isValid():
            return

        run = self.model.getRun(current_index)
        if not run:
            return

        run_id = run.get("id")
        ingest_post_id = run.get("ingest_post_id")

        # Clear previous DOM safely
        self.dom_tree_view.setModel(None)
        self.dom_model = None
        self.save_button.setEnabled(False)

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

            self.current_dom_tree, self.dom_snapshot_id = build_dom_for_first_review(
                conn=conn,
                ingest_post_id=ingest_post_id,
                lss_run_id=run_id,
            )

            self.dom_model = DomTreeModel(self.current_dom_tree)
            self.dom_tree_view.setModel(self.dom_model)
            self.dom_tree_view.expandAll()

            self.node_detail_label.setText("Node details will appear here")
            self.save_button.setEnabled(True)
        finally:
            conn.close()

    def save_dom_tree(self):
        if not self.current_dom_tree or self.dom_snapshot_id is None:
            return

        conn = sqlite3.connect(records_path())
        try:
            persist_dom_tree(
                conn=conn,
                dom_snapshot_id=self.dom_snapshot_id,
                root=self.current_dom_tree,
            )
        finally:
            conn.close()

    def _load_runs(self) -> list[dict]:
        conn = sqlite3.connect(records_path())
        try:
            cur = conn.cursor()
            cur.execute("""
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
            """)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            conn.close()

