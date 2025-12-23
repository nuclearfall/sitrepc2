from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    Qt,
)

from sitrepc2.dom.dom_report import ReportNode


# ============================================================
# CUSTOM ROLES (GUI-SPECIFIC)
# ============================================================

NodeTypeRole = Qt.UserRole + 1
NodeIdRole = Qt.UserRole + 2
ReviewStageRole = Qt.UserRole + 3
InspectionRole = Qt.UserRole + 4
ResolutionStateRole = Qt.UserRole + 5
ConfidenceRole = Qt.UserRole + 6


# ============================================================
# TREE MODEL
# ============================================================

class ReportTreeModel(QAbstractItemModel):
    """
    TreeView model for DOM review.

    - Pure adapter over ReportNode trees
    - Selection-only interaction
    - No domain logic
    - No persistence
    """

    def __init__(self, roots: List[ReportNode], parent=None) -> None:
        super().__init__(parent)
        self._roots = roots

    # --------------------------------------------------------
    # Qt required overrides
    # --------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not parent.isValid():
            return len(self._roots)
        node = parent.internalPointer()
        return len(node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def index(
        self,
        row: int,
        column: int,
        parent: QModelIndex = QModelIndex(),
    ) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            node = self._roots[row]
        else:
            parent_node = parent.internalPointer()
            node = parent_node.children[row]

        return self.createIndex(row, column, node)

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        node: ReportNode = index.internalPointer()
        parent_node = self._find_parent(node)

        if parent_node is None:
            return QModelIndex()

        row = self._row_of_node(parent_node)
        return self.createIndex(row, 0, parent_node)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        node: ReportNode = index.internalPointer()

        if role == Qt.DisplayRole:
            return node.summary

        if role == Qt.CheckStateRole:
            return Qt.Checked if node.selected else Qt.Unchecked

        if role == NodeTypeRole:
            return node.node_type

        if role == NodeIdRole:
            return node.node_id

        if role == ReviewStageRole:
            return node.review_stage

        if role == InspectionRole:
            return node.inspection

        if role == ResolutionStateRole:
            return node.inspection.get("resolution_state")

        if role == ConfidenceRole:
            return node.inspection.get("confidence")

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags

        return (
            Qt.ItemIsEnabled
            | Qt.ItemIsSelectable
            | Qt.ItemIsUserCheckable
        )

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.EditRole,
    ) -> bool:
        if role != Qt.CheckStateRole or not index.isValid():
            return False

        node: ReportNode = index.internalPointer()
        new_state = value == Qt.Checked

        if node.selected == new_state:
            return False

        self._set_selected(node, new_state)
        self.dataChanged.emit(index, index, [Qt.CheckStateRole])
        return True

    # --------------------------------------------------------
    # Selection propagation
    # --------------------------------------------------------

    def _set_selected(self, node: ReportNode, selected: bool) -> None:
        node.selected = selected

        # Downward propagation
        for child in node.children:
            self._set_selected(child, selected)

        # Upward propagation
        parent = self._find_parent(node)
        if parent:
            parent.selected = any(c.selected for c in parent.children)

    # --------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------

    def _find_parent(self, node: ReportNode) -> Optional[ReportNode]:
        for root in self._roots:
            found = self._find_parent_rec(root, node)
            if found:
                return found
        return None

    def _find_parent_rec(
        self,
        current: ReportNode,
        target: ReportNode,
    ) -> Optional[ReportNode]:
        for child in current.children:
            if child is target:
                return current
            found = self._find_parent_rec(child, target)
            if found:
                return found
        return None

    def _row_of_node(self, node: ReportNode) -> int:
        parent = self._find_parent(node)
        if parent is None:
            return self._roots.index(node)
        return parent.children.index(node)
