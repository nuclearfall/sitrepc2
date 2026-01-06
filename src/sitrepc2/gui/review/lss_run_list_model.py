from __future__ import annotations

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


class LssRunListModel(QAbstractTableModel):
    """
    Table model for LSS runs with a UI-only checkbox column.

    Column 0: checkbox (pending DOM preparation)
    Columns 1..N: run metadata (read-only)
    """

    COLUMN_HEADERS = [
        "",             # checkbox
        "Source",
        "Publisher",
        "Published At",
        "Fetched At",
    ]

    def __init__(self, runs: list[dict], parent=None):
        super().__init__(parent)
        self._runs = runs
        self._checked: set[int] = set()   # row indices only (UI state)

    # ------------------------------------------------------------------
    # Qt model basics
    # ------------------------------------------------------------------

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._runs)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMN_HEADERS)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        run = self._runs[row]

        # Checkbox column
        if col == 0:
            if role == Qt.CheckStateRole:
                return Qt.Checked if row in self._checked else Qt.Unchecked
            return None

        if role != Qt.DisplayRole:
            return None

        return (
            run.get("source", ""),
            run.get("publisher", ""),
            run.get("published_at", ""),
            run.get("fetched_at", ""),
        )[col - 1]

    # ------------------------------------------------------------------
    # Editing (checkbox only)
    # ------------------------------------------------------------------

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        if not index.isValid():
            return False

        if index.column() != 0 or role != Qt.CheckStateRole:
            return False

        row = index.row()
        if value == Qt.Checked:
            self._checked.add(row)
        else:
            self._checked.discard(row)

        self.dataChanged.emit(index, index, [Qt.CheckStateRole])
        return True

    # ------------------------------------------------------------------
    # Flags
    # ------------------------------------------------------------------

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags

        if index.column() == 0:
            return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable

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
    # Public helpers (used by workspace controller)
    # ------------------------------------------------------------------

    def get_run(self, index: QModelIndex) -> dict | None:
        """
        Return the run dict for a selected row (focus).
        """
        if not index.isValid():
            return None
        return self._runs[index.row()]

    def get_checked_runs(self) -> list[dict]:
        """
        Return run dicts whose checkbox is checked.
        Order is stable and follows table order.
        """
        return [self._runs[i] for i in sorted(self._checked)]

    def clear_checks(self) -> None:
        """
        Clear all checkbox state.
        """
        if not self._checked:
            return
        self._checked.clear()
        top_left = self.index(0, 0)
        bottom_right = self.index(self.rowCount() - 1, 0)
        self.dataChanged.emit(
            top_left,
            bottom_right,
            [Qt.CheckStateRole],
        )
