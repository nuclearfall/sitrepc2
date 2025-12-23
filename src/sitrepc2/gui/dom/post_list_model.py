from __future__ import annotations

from typing import Any, List

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Qt,
)

from sitrepc2.dom.dom_report import ReportNode


# ============================================================
# CUSTOM ROLES
# ============================================================

PostNodeRole = Qt.UserRole + 1
PostIdRole = Qt.UserRole + 2
ReviewStageRole = Qt.UserRole + 3
InspectionRole = Qt.UserRole + 4


# ============================================================
# LIST MODEL
# ============================================================

class PostListModel(QAbstractListModel):
    """
    Flat list model for Post-level review.

    This model:
    - exposes Post ReportNodes only
    - mirrors selection state
    - does NOT own tree structure
    """

    def __init__(self, posts: List[ReportNode], parent=None) -> None:
        super().__init__(parent)
        self._posts = posts

    # --------------------------------------------------------
    # Required Qt Overrides
    # --------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._posts)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        post = self._posts[index.row()]

        if role == Qt.DisplayRole:
            return post.summary

        if role == Qt.CheckStateRole:
            return Qt.Checked if post.selected else Qt.Unchecked

        if role == PostNodeRole:
            return post

        if role == PostIdRole:
            return post.inspection.get("ingest_post_id")

        if role == ReviewStageRole:
            return post.review_stage

        if role == InspectionRole:
            return post.inspection

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

        post = self._posts[index.row()]
        new_state = value == Qt.Checked

        if post.selected == new_state:
            return False

        post.selected = new_state

        # Selection here does NOT automatically mutate children.
        # TreeView selection propagation handles that.
        self.dataChanged.emit(index, index, [Qt.CheckStateRole])
        return True

    # --------------------------------------------------------
    # Convenience
    # --------------------------------------------------------

    def post_at(self, row: int) -> ReportNode:
        return self._posts[row]
