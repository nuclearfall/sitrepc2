from PySide6.QtWidgets import (
    QWidget, QSplitter, QTableView, QPlainTextEdit, QLabel, QVBoxLayout,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt

from .lss_run_model import LssRunModel  # assumed to exist and handle run data


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
        self.dom_tree_placeholder = QLabel("👆 Select a run to load DOM snapshot")
        self.dom_tree_placeholder.setAlignment(Qt.AlignCenter)
        right_splitter.addWidget(self.dom_tree_placeholder)

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
        # You’ll later connect this to database query:
        self.text_edit.setPlainText(f"<stub text for run_id={run_id}>")
        self.dom_tree_placeholder.setText(f"DOM tree for run {run_id} would be displayed here.")
        self.node_detail_placeholder.setText("Node details will appear here")
