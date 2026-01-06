from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

class LssRunModel(QAbstractTableModel):
    """Table model for LSS runs, each row is a run with source, publisher, published_at, fetched_at."""
    COLUMN_HEADERS = ["Source", "Publisher", "Published At", "Fetched At"]
    
    def __init__(self, runs: list[dict], parent=None):
        super().__init__(parent)
        self._runs = runs
    
    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._runs)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMN_HEADERS)
    
    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            run = self._runs[index.row()]
            col = index.column()
            if col == 0:
                return run.get("source", "")
            elif col == 1:
                return run.get("publisher", "")
            elif col == 2:
                return run.get("published_at", "")
            elif col == 3:
                return run.get("fetched_at", "")
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self.COLUMN_HEADERS):
            return self.COLUMN_HEADERS[section]
        return super().headerData(section, orientation, role)
    
    def flags(self, index: QModelIndex):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled
    
    def getRun(self, index: QModelIndex) -> dict:
        if index.isValid():
            return self._runs[index.row()]
        return None
