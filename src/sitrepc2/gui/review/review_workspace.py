from __future__ import annotations

from typing import Optional, Dict

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

from sitrepc2.gui.ingest.controller import (
    IngestController,
    IngestPostFilter,
    IngestPostState,
)

from sitrepc2.gui.review.controller import ReviewController
from sitrepc2.dom.nodes import BaseNode


# ============================================================================
# Review Workspace
# ============================================================================

class ReviewWorkspace(QWidget):
    """
    UI workspace for DOM review.

    Pure UI responsibilities:
    - Display READY_FOR_REVIEW posts
    - Display DOM tree for selected post
    - Reflect and update node selection state
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.ingest = IngestController()
        self.review = ReviewController(self.ingest.records_db_path)

        self._current_snapshot_id: Optional[int] = None
        self._dom_nodes: Dict[str, BaseNode] = {}

        self._build_ui()
        self._load_posts()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Review Extracted Posts"))

        splitter = QSplitter(Qt.Horizontal)

        # --------------------------------------------------------------
        # Left: Post list
        # --------------------------------------------------------------

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Published", "Alias", "Source", "Events", "Snippet"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_post_selected)

        splitter.addWidget(self.table)

        # --------------------------------------------------------------
        # Right: DOM tree
        # --------------------------------------------------------------

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Node", "Type"])
        self.tree.itemChanged.connect(self._on_item_check_changed)

        splitter.addWidget(self.tree)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter)

    # ------------------------------------------------------------------
    # Post loading
    # ------------------------------------------------------------------

    def _load_posts(self) -> None:
        rows = self.ingest.query_posts(
            IngestPostFilter(state=IngestPostState.READY_FOR_REVIEW)
        )

        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            items = [
                QTableWidgetItem(row.published_at),
                QTableWidgetItem(row.alias),
                QTableWidgetItem(row.source),
                QTableWidgetItem(str(row.event_count)),
                QTableWidgetItem(row.text_snippet),
            ]
            for c, item in enumerate(items):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, item)

        self.table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # Post selection
    # ------------------------------------------------------------------

    def _on_post_selected(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return

        row_idx = items[0].row()
        rows = self.ingest.query_posts(
            IngestPostFilter(state=IngestPostState.READY_FOR_REVIEW)
        )

        post_id = rows[row_idx].post_id
        lss_run_id = self.ingest.get_latest_lss_run_id(post_id)
        if not lss_run_id:
            return

        snapshot_id, nodes = self.review.enter_initial_review(
            ingest_post_id=post_id,
            lss_run_id=lss_run_id,
        )

        self._current_snapshot_id = snapshot_id
        self._dom_nodes = nodes

        self._rebuild_dom_tree()

    # ------------------------------------------------------------------
    # DOM tree rendering
    # ------------------------------------------------------------------

    def _rebuild_dom_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()

        post_node = next(
            n for n in self._dom_nodes.values()
            if n.node_id.startswith("post:")
        )

        root_item = self._build_tree_item(post_node)
        self.tree.addTopLevelItem(root_item)
        root_item.setExpanded(True)

        self.tree.blockSignals(False)

    def _build_tree_item(self, node: BaseNode) -> QTreeWidgetItem:
        selected = self.review.get_node_selection(
            dom_snapshot_id=self._current_snapshot_id,
            dom_node_id=node.node_id,
        )

        item = QTreeWidgetItem([node.summary, node.node_type])
        item.setData(0, Qt.UserRole, node.node_id)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(0, Qt.Checked if selected else Qt.Unchecked)

        for child in node.children:
            item.addChild(self._build_tree_item(child))

        return item

    # ------------------------------------------------------------------
    # Selection propagation
    # ------------------------------------------------------------------

    def _on_item_check_changed(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        if column != 0 or self._current_snapshot_id is None:
            return

        node_id = item.data(0, Qt.UserRole)
        checked = item.checkState(0) == Qt.Checked

        # Persist this node
        self.review.set_node_selected(
            dom_snapshot_id=self._current_snapshot_id,
            dom_node_id=node_id,
            selected=checked,
        )

        # Propagate to children
        self._propagate_to_children(item, checked)

        # Update parents
        self._update_parent_state(item.parent())

    def _propagate_to_children(
        self,
        item: QTreeWidgetItem,
        selected: bool,
    ) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, Qt.Checked if selected else Qt.Unchecked)

            self.review.set_node_selected(
                dom_snapshot_id=self._current_snapshot_id,
                dom_node_id=child.data(0, Qt.UserRole),
                selected=selected,
            )

            self._propagate_to_children(child, selected)

    def _update_parent_state(
        self,
        parent: Optional[QTreeWidgetItem],
    ) -> None:
        if not parent:
            return

        checked = 0
        unchecked = 0

        for i in range(parent.childCount()):
            state = parent.child(i).checkState(0)
            if state == Qt.Checked:
                checked += 1
            elif state == Qt.Unchecked:
                unchecked += 1

        if checked == parent.childCount():
            parent.setCheckState(0, Qt.Checked)
            selected = True
        elif unchecked == parent.childCount():
            parent.setCheckState(0, Qt.Unchecked)
            selected = False
        else:
            parent.setCheckState(0, Qt.PartiallyChecked)
            selected = False

        self.review.set_node_selected(
            dom_snapshot_id=self._current_snapshot_id,
            dom_node_id=parent.data(0, Qt.UserRole),
            selected=selected,
        )

        self._update_parent_state(parent.parent())
