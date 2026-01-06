from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt, QAbstractTableModel

class LssRunModel(QAbstractTableModel):
    """Table model for LSS runs, each row is a run with source, publisher, published_at, fetched_at."""
    COLUMN_HEADERS = ["Source", "Publisher", "Published At", "Fetched At"]
    
    def __init__(self, runs: list[dict], parent=None):
        super().__init__(parent)
        self._runs = runs  # List of dicts or objects with keys: source, publisher, published_at, fetched_at, id, etc.
    
    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._runs)
    
    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.COLUMN_HEADERS)
    
    def data(self, index: QtCore.QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            run = self._runs[index.row()]
            col = index.column()
            # Return the appropriate field based on column
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
        if orientation == Qt.Horizontal:
            # Return column names for horizontal header
            if 0 <= section < len(self.COLUMN_HEADERS):
                return self.COLUMN_HEADERS[section]
        else:
            return super().headerData(section, orientation, role)
    
    def flags(self, index: QtCore.QModelIndex):
        # Make cells enabled and selectable (not editable by user)
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled
    
    def getRun(self, index: QtCore.QModelIndex) -> dict:
        """Utility to retrieve the run data (as dict) for a given model index."""
        if index.isValid():
            return self._runs[index.row()]
        return None
