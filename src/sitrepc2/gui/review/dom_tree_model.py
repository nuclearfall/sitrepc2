from PySide6.QtCore import Qt, QAbstractItemModel, QModelIndex
from sitrepc2.dom.nodes import DomNode, Context


class _ContextRow:
    """
    Lightweight adapter so Context can appear as a tree row.
    """
    def __init__(self, parent: DomNode, context: Context):
        self.parent = parent
        self.context = context
        self.children = []  # leaf

    @property
    def selected(self) -> bool:
        return self.context.selected

    @selected.setter
    def selected(self, value: bool):
        object.__setattr__(self.context, "selected", value)

    @property
    def summary(self) -> str:
        return f"[{self.context.ctx_kind}] {self.context.value}"


class DomTreeModel(QAbstractItemModel):
    def __init__(self, root: DomNode, parent=None):
        super().__init__(parent)
        self.root = root

    # ------------------------------------------------------------------
    # Index / Parent
    # ------------------------------------------------------------------

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        parent_node = parent.internalPointer() if parent.isValid() else self.root
        children = self._children_of(parent_node)

        if 0 <= row < len(children):
            return self.createIndex(row, column, children[row])

        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        node = index.internalPointer()
        parent = getattr(node, "parent", None)
        if parent is None or parent == self.root:
            return QModelIndex()

        grandparent = getattr(parent, "parent", None)
        if grandparent is None:
            return QModelIndex()

        row = self._children_of(grandparent).index(parent)
        return self.createIndex(row, 0, parent)

    # ------------------------------------------------------------------
    # Structure helpers
    # ------------------------------------------------------------------

    def _children_of(self, node):
        if isinstance(node, _ContextRow):
            return []
        rows = []
        rows.extend(node.children)
        for ctx in getattr(node, "contexts", []):
            rows.append(_ContextRow(node, ctx))
        return rows

    # ------------------------------------------------------------------
    # Counts
    # ------------------------------------------------------------------

    def rowCount(self, parent=QModelIndex()):
        node = parent.internalPointer() if parent.isValid() else self.root
        return len(self._children_of(node))

    def columnCount(self, parent=QModelIndex()):
        return 1

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        node = index.internalPointer()

        if role == Qt.DisplayRole:
            if isinstance(node, _ContextRow):
                return node.summary
            return self._label_for_node(node)

        if role == Qt.CheckStateRole:
            return Qt.Checked if getattr(node, "selected", False) else Qt.Unchecked

        return None

    def _label_for_node(self, node: DomNode) -> str:
        t = node.__class__.__name__.replace("Node", "")
        if node.summary:
            return f"{t}: {node.summary}"
        return t

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------

    def setData(self, index, value, role):
        if role != Qt.CheckStateRole or not index.isValid():
            return False

        node = index.internalPointer()
        checked = value == Qt.Checked

        self._set_selected_recursive(node, checked)
        self.layoutChanged.emit()
        return True

    def _set_selected_recursive(self, node, selected: bool):
        node.selected = selected
        for child in self._children_of(node):
            self._set_selected_recursive(child, selected)

    # ------------------------------------------------------------------
    # Flags
    # ------------------------------------------------------------------

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable
