from PySide6.QtWidgets import (
    QWidget, QSplitter, QTableView, QPlainTextEdit, QTreeView, QLabel, QVBoxLayout,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt
import sqlite3

from sitrepc2.gui.review.lss_run_model import LssRunModel
from sitrepc2.gui.review.dom_tree_model import DomTreeModel
from sitrepc2.dom.dom_first_review import build_dom_for_first_review
from sitrepc2.paths import records_path


def query_context_hints(conn: sqlite3.Connection, lss_run_id: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ctx_kind, text, start_token, end_token, scope, target_id, source
        FROM lss_context_hints
        WHERE lss_run_id = ?
        """,
        (lss_run_id,)
    )
    rows = cur.fetchall()
    return [
        {
            "ctx_kind": row[0],
            "text": row[1],
            "start_token": row[2],
            "end_token": row[3],
            "scope": row[4],
            "target_id": row[5],
            "source": row[6],
        }
        for row in rows
    ]


class DomReviewWorkspace(QWidget):
    def __init__(self, runs_data, parent=None):
        super().__init__(parent)

        # Main layout container
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        # Main horizontal splitter (left and right panels)
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)

        # Left vertical splitter (Run list + post text)
        left_splitter = QSplitter(Qt.Vertical)

        self.model = LssRunModel(runs_data, parent=self)
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

        # Right vertical splitter (DOM tree + node details)
        right_splitter = QSplitter(Qt.Vertical)

        self.dom_tree_view = QTreeView()
        self.dom_tree_view.setHeaderHidden(True)
        right_splitter.addWidget(self.dom_tree_view)

        self.node_detail_placeholder = QLabel("Node details will appear here")
        self.node_detail_placeholder.setAlignment(Qt.AlignCenter)
        right_splitter.addWidget(self.node_detail_placeholder)

        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)

        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_splitter)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)

        self.table_view.selectionModel().currentChanged.connect(self.on_run_selected)

        if self.model.rowCount() > 0:
            first_index = self.model.index(0, 0)
            self.table_view.setCurrentIndex(first_index)

    def on_run_selected(self, current_index, previous_index):
        run = self.model.getRun(current_index)
        if not run:
            return

        run_id = run.get("id")
        ingest_post_id = run.get("ingest_post_id")

        conn = sqlite3.connect(records_path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            text_query = """
                SELECT ip.text
                FROM ingest_posts ip
                JOIN lss_runs lr ON lr.ingest_post_id = ip.id
                WHERE lr.id = ?
            """
            cur = conn.cursor()
            cur.execute(text_query, (run_id,))
            row = cur.fetchone()
            self.text_edit.setPlainText(row[0] if row else "")

            # Load or create the DOM tree
            context_hints = query_context_hints(conn=conn, lss_run_id=run_id)
            root_node = build_dom_for_first_review(
                conn=conn,
                ingest_post_id=ingest_post_id,
                lss_run_id=run_id,
                context_hints=context_hints,
            )

            # Populate tree view
            model = DomTreeModel(root_node)
            self.dom_tree_view.setModel(model)
            self.dom_tree_view.expandAll()

            # Reset details panel
            self.node_detail_placeholder.setText("Node details will appear here")

        finally:
            conn.close()
