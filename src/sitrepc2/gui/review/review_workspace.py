from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QSplitter,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QAbstractItemView,
)

from sitrepc2.gui.review.controller import ReviewController


# ============================================================================
# Review Workspace
# ============================================================================

class ReviewWorkspace(QWidget):
    """
    DOM-backed review workspace.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.review = ReviewController()

        self._current_snapshot_id: Optional[int] = None
        self._nodes_by_id: Dict[int, QTreeWidgetItem] = {}

        self._build_ui()
        self._load_runs()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(QLabel("DOM Review"))

        splitter = QSplitter(Qt.Horizontal)

        # --------------------------------------------------
        # Runs table
        # --------------------------------------------------

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Ingest Post", "LSS Run", "Events", "Started"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_run_selected)

        splitter.addWidget(self.table)

        # --------------------------------------------------
        # DOM tree
        # --------------------------------------------------

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Node", "Type"])
        self.tree.itemChanged.connect(self._on_item_changed)

        splitter.addWidget(self.tree)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def _load_runs(self) -> None:
        runs = self.review.list_reviewable_runs()

        self.table.setRowCount(len(runs))

        for r, row in enumerate(runs):
            self.table.setItem(r, 0, QTableWidgetItem(str(row["ingest_post_id"])))
            self.table.setItem(r, 1, QTableWidgetItem(str(row["lss_run_id"])))
            self.table.setItem(r, 2, QTableWidgetItem(str(row["event_count"])))
            self.table.setItem(r, 3, QTableWidgetItem(row["started_at"]))

        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # Run selection
    # ------------------------------------------------------------------

    def _on_run_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return

        row = items[0].row()

        ingest_post_id = int(self.table.item(row, 0).text())
        lss_run_id = int(self.table.item(row, 1).text())

        snapshot_id = self.review.enter_initial_review(
            ingest_post_id=ingest_post_id,
            lss_run_id=lss_run_id,
        )

        self._current_snapshot_id = snapshot_id
        self._load_dom_tree()

    # ------------------------------------------------------------------
    # Tree
    # ------------------------------------------------------------------

    def _load_dom_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        self._nodes_by_id.clear()

        rows = self.review.load_dom_tree(
            dom_snapshot_id=self._current_snapshot_id
        )

        # First pass: create items
        for row in rows:
            item = QTreeWidgetItem([row["summary"], row["node_type"]])
            item.setData(0, Qt.UserRole, row["node_id"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                0, Qt.Checked if row["selected"] else Qt.Unchecked
            )
            self._nodes_by_id[row["node_id"]] = item

        # Second pass: parent/child wiring
        for row in rows:
            item = self._nodes_by_id[row["node_id"]]
            parent_id = row["parent_id"]

            if parent_id is None:
                self.tree.addTopLevelItem(item)
                item.setExpanded(True)
            else:
                self._nodes_by_id[parent_id].addChild(item)

        self.tree.blockSignals(False)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_item_changed(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        if column != 0 or self._current_snapshot_id is None:
            return

        node_id = item.data(0, Qt.UserRole)
        selected = item.checkState(0) == Qt.Checked

        self.review.set_node_selected(
            dom_snapshot_id=self._current_snapshot_id,
            dom_node_id=node_id,
            selected=selected,
        )
