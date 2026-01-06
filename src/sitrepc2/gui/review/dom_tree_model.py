from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex
from sitrepc2.dom.nodes import DomNode


class DomTreeModel(QAbstractItemModel):
    def __init__(self, root: DomNode):
        super().__init__()
        self.root = root

    def index(self, row: int, column: int, parent: QModelIndex) -> QModelIndex:
        parent_node = parent.internalPointer() if parent.isValid() else self.root
        if 0 <= row < len(parent_node.children):
            return self.createIndex(row, column, parent_node.children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node = index.internalPointer()
        parent = node.parent
        if parent is None or parent == self.root:
            return QModelIndex()
        grandparent = parent.parent
        row = grandparent.children.index(parent) if grandparent else 0
        return self.createIndex(row, 0, parent)

    def rowCount(self, parent: QModelIndex) -> int:
        node = parent.internalPointer() if parent.isValid() else self.root
        return len(node.children)

    def columnCount(self, parent: QModelIndex) -> int:
        return 1

    def data(self, index: QModelIndex, role: int):
        if not index.isValid():
            return None
        node = index.internalPointer()
        if role == Qt.DisplayRole:
            return node.summary
        elif role == Qt.CheckStateRole:
            return Qt.Checked if node.selected else Qt.Unchecked
        return None

    def setData(self, index: QModelIndex, value, role: int):
        if not index.isValid():
            return False
        node: DomNode = index.internalPointer()
        if role == Qt.CheckStateRole:
            node.selected = value == Qt.Checked
            self.dataChanged.emit(index, index, [Qt.CheckStateRole])
            return True
        return False

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable

    def headerData(self, section: int, orientation, role: int):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return "DOM Node Summary"
        return None