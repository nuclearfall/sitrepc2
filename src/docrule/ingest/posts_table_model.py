from __future__ import annotations

from typing import Any, List

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
)

from sitrepc2.gui.ingest.ingest_controller import IngestController
from sitrepc2.gui.ingest.typedefs import IngestPostEntry, IngestState


# ============================================================
# COLUMN DEFINITIONS
# ============================================================

COL_INCLUDE = 0
COL_ALIAS = 1
COL_PUBLISHER = 2
COL_PUBLISHED_AT = 3
COL_LANG = 4
COL_STATE = 5
COL_TEXT = 6

COLUMNS = [
    "Include",
    "Alias",
    "Publisher",
    "Published",
    "Lang",
    "State",
    "Text",
]


# ============================================================
# MODEL
# ============================================================

class IngestPostsTableModel(QAbstractTableModel):
    """
    QTableView adapter for ingest_posts.

    Responsibilities:
    - display posts
    - include/exclude selection
    - reflect derived ingest state

    No persistence or extraction logic.
    """

    def __init__(
        self,
        controller: IngestController,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller

    # --------------------------------------------------------
    # Qt required overrides
    # --------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._controller.filtered_posts())

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> Any:
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return COLUMNS[section]

        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        post = self._controller.filtered_posts()[index.row()]
        col = index.column()

        # ----------------------------
        # Display
        # ----------------------------

        if role == Qt.DisplayRole:
            if col == COL_ALIAS:
                return post.alias
            if col == COL_PUBLISHER:
                return post.publisher
            if col == COL_PUBLISHED_AT:
                return post.published_at.isoformat(sep=" ", timespec="minutes")
            if col == COL_LANG:
                return post.lang
            if col == COL_STATE:
                return post.state.value
            if col == COL_TEXT:
                return post.text

        # ----------------------------
        # Checkbox
        # ----------------------------

        if role == Qt.CheckStateRole and col == COL_INCLUDE:
            return (
                Qt.Checked
                if post.post_id in self._controller.included_post_ids
                else Qt.Unchecked
            )

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags

        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        if index.column() == COL_INCLUDE:
            flags |= Qt.ItemIsUserCheckable

        return flags

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.EditRole,
    ) -> bool:
        if not index.isValid():
            return False

        if role != Qt.CheckStateRole or index.column() != COL_INCLUDE:
            return False

        post = self._controller.filtered_posts()[index.row()]
        included = value == Qt.Checked

        self._controller.toggle_post_included(
            post_id=post.post_id,
            included=included,
        )

        self.dataChanged.emit(index, index, [Qt.CheckStateRole])
        return True

    # --------------------------------------------------------
    # Refresh
    # --------------------------------------------------------

    def refresh(self) -> None:
        self.beginResetModel()
        self.endResetModel()
