from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
)

from sitrepc2.gui.ingest.ingest_controller import IngestController
from sitrepc2.gui.ingest.typedefs import SourceEntry


# ============================================================
# COLUMNS
# ============================================================

COL_ACTIVE = 0
COL_SOURCE_NAME = 1
COL_ALIAS = 2
COL_KIND = 3
COL_LANG = 4

COLUMNS = [
    "Active",
    "Source Name",
    "Alias",
    "Kind",
    "Lang",
]


# ============================================================
# MODEL
# ============================================================

class SourcesTableModel(QAbstractTableModel):
    """
    Editable table model for sources.jsonl.

    Inline editing only — no dialogs.
    Persistence is handled by the controller.
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
        return len(self._controller.sources)

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

        src = self._controller.sources[index.row()]
        col = index.column()

        if role == Qt.DisplayRole or role == Qt.EditRole:
            if col == COL_SOURCE_NAME:
                return src.source_name
            if col == COL_ALIAS:
                return src.alias
            if col == COL_KIND:
                return src.source_kind
            if col == COL_LANG:
                return src.lang

        if role == Qt.CheckStateRole and col == COL_ACTIVE:
            return Qt.Checked if src.active else Qt.Unchecked

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags

        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        if index.column() == COL_ACTIVE:
            flags |= Qt.ItemIsUserCheckable

        if index.column() in (
            COL_SOURCE_NAME,
            COL_ALIAS,
            COL_KIND,
            COL_LANG,
        ):
            flags |= Qt.ItemIsEditable

        return flags

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.EditRole,
    ) -> bool:
        if not index.isValid():
            return False

        src = self._controller.sources[index.row()]
        col = index.column()

        if col == COL_ACTIVE and role == Qt.CheckStateRole:
            src.active = value == Qt.Checked
            self._controller.toggle_source_active(
                src.source_name,
                src.active,
            )
        elif role == Qt.EditRole:
            if col == COL_SOURCE_NAME:
                src.source_name = str(value)
            elif col == COL_ALIAS:
                src.alias = str(value)
            elif col == COL_KIND:
                src.source_kind = str(value)
            elif col == COL_LANG:
                src.lang = str(value)
            else:
                return False
        else:
            return False

        self.dataChanged.emit(index, index)
        return True

    # --------------------------------------------------------
    # Row management
    # --------------------------------------------------------

    def add_empty_source(self) -> None:
        """
        Append a new editable source row.
        """
        self.beginInsertRows(
            QModelIndex(),
            len(self._controller.sources),
            len(self._controller.sources),
        )

        self._controller.sources.append(
            SourceEntry(
                source_name="",
                alias="",
                source_kind="",
                lang="",
                active=False,
            )
        )

        self.endInsertRows()

    # --------------------------------------------------------
    # Refresh
    # --------------------------------------------------------

    def refresh(self) -> None:
        self.beginResetModel()
        self.endResetModel()
