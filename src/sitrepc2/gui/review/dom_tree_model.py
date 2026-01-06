from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex
from sitrepc2.dom.nodes import DomNode

 
class DomTreeModel(QAbstractItemModel):
    def __init__(self, root: DomNode):
        super().__init__()
        self.root = root

    # -------------------------
    # Index / Parent
    # -------------------------

    def index(self, row, column, parent=QModelIndex()):
        try:
            parent_node = parent.internalPointer() if parent.isValid() else self.root
            if (
                parent_node
                and hasattr(parent_node, "children")
                and 0 <= row < len(parent_node.children)
            ):
                return self.createIndex(row, column, parent_node.children[row])
        except Exception:
            pass
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        try:
            node = index.internalPointer()
            parent = getattr(node, "parent", None)
            if parent is None or parent == self.root:
                return QModelIndex()

            grandparent = getattr(parent, "parent", None)
            if not grandparent or not hasattr(grandparent, "children"):
                return QModelIndex()

            row = grandparent.children.index(parent)
            return self.createIndex(row, 0, parent)
        except Exception:
            return QModelIndex()

    # -------------------------
    # Counts
    # -------------------------

    def rowCount(self, parent=QModelIndex()):
        try:
            node = parent.internalPointer() if parent.isValid() else self.root
            return len(node.children) if node and hasattr(node, "children") else 0
        except Exception:
            return 0

    def columnCount(self, parent=QModelIndex()):
        return 1

    # -------------------------
    # Data
    # -------------------------

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return ""

        try:
            node = index.internalPointer()
            if role == Qt.DisplayRole:
                return getattr(node, "summary", "")
            if role == Qt.CheckStateRole:
                return Qt.Checked if getattr(node, "selected", False) else Qt.Unchecked
        except Exception:
            return ""

        return ""

    def setData(self, index, value, role):
        if not index.isValid():
            return False

        try:
            node = index.internalPointer()
            if role == Qt.CheckStateRole:
                node.selected = value == Qt.Checked
                self.dataChanged.emit(index, index, [Qt.CheckStateRole])
                return True
        except Exception:
            return False

        return False

    # -------------------------
    # Flags / Header
    # -------------------------

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return (
            Qt.ItemIsEnabled
            | Qt.ItemIsSelectable
            | Qt.ItemIsUserCheckable
        )

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return "DOM Node Summary"
        return ""
