from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

class LssRunModel(QAbstractTableModel):
    COLUMN_HEADERS = ["Source", "Publisher", "Published At", "Fetched At"]

    def __init__(self, runs: list[dict] | None, parent=None):
        super().__init__(parent)
        self._runs = runs or []

    def rowCount(self, parent=QModelIndex()) -> int:
        try:
            return int(len(self._runs))
        except Exception:
            return 0

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMN_HEADERS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return ""

        try:
            run = self._runs[index.row()]
        except Exception:
            return ""

        return (
            run.get("source", ""),
            run.get("publisher", ""),
            run.get("published_at", ""),
            run.get("fetched_at", ""),
        )[index.column()]

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self.COLUMN_HEADERS):
                return self.COLUMN_HEADERS[section]
        return ""

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def getRun(self, index: QModelIndex) -> dict | None:
        if index.isValid():
            try:
                return self._runs[index.row()]
            except Exception:
                return None
        return None

