from __future__ import annotations

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


class LssRunListModel(QAbstractTableModel):
    COLUMN_HEADERS = [
        "Source",
        "Publisher",
        "Published At",
        "Fetched At",
    ]

    def __init__(self, runs: list[dict], parent=None):
        super().__init__(parent)
        self._runs = runs

    # ------------------------------------------------------------------
    # Qt basics
    # ------------------------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._runs)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMN_HEADERS)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None

        run = self._runs[index.row()]

        return (
            run.get("source", ""),
            run.get("publisher", ""),
            run.get("published_at", ""),
            run.get("fetched_at", ""),
        )[index.column()]

    # ------------------------------------------------------------------
    # Flags
    # ------------------------------------------------------------------

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    # ------------------------------------------------------------------
    # Headers
    # ------------------------------------------------------------------

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if (
            role == Qt.DisplayRole
            and orientation == Qt.Horizontal
            and 0 <= section < len(self.COLUMN_HEADERS)
        ):
            return self.COLUMN_HEADERS[section]
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_run(self, index: QModelIndex) -> dict | None:
        if not index.isValid():
            return None
        return self._runs[index.row()]
