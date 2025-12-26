# src/dbeditc2/widgets/navigation_tree.py
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from dbeditc2.enums import CollectionKind


class NavigationTree(QTreeWidget):
    """
    Semantic navigation tree for the editor.

    Presents conceptual groupings (Gazetteer, Lexicon),
    not database tables or schema elements.
    """

    collectionSelected = Signal(CollectionKind)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setHeaderHidden(True)

        self._item_to_collection: dict[QTreeWidgetItem, CollectionKind] = {}

        self._build_tree()
        self.itemSelectionChanged.connect(self._on_selection_changed)

        # 🔹 IMPORTANT: select default collection
        self._select_default()

    def _build_tree(self) -> None:
        # Root items
        gazetteer_root = QTreeWidgetItem(self, ["Gazetteer"])
        lexicon_root = QTreeWidgetItem(self, ["Lexicon"])

        # Gazetteer collections
        self._add_child(gazetteer_root, "Locations", CollectionKind.LOCATIONS)
        self._add_child(gazetteer_root, "Regions", CollectionKind.REGIONS)
        self._add_child(gazetteer_root, "Groups", CollectionKind.GROUPS)
        self._add_child(gazetteer_root, "Directions", CollectionKind.DIRECTIONS)

        # Lexicon collections
        self._add_child(lexicon_root, "Event phrases", CollectionKind.EVENT_PHRASES)
        self._add_child(lexicon_root, "Context phrases", CollectionKind.CONTEXT_PHRASES)

        self.expandAll()

    def _add_child(
        self,
        parent: QTreeWidgetItem,
        label: str,
        collection: CollectionKind,
    ) -> None:
        item = QTreeWidgetItem(parent, [label])
        self._item_to_collection[item] = collection

    def _on_selection_changed(self) -> None:
        selected_items = self.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        collection = self._item_to_collection.get(item)
        if collection is not None:
            self.collectionSelected.emit(collection)

    def _select_default(self) -> None:
        """
        Select the default collection on startup.
        """
        # Default to Locations
        self.set_current(CollectionKind.LOCATIONS)

    def set_current(self, collection: CollectionKind) -> None:
        """
        Programmatically select a collection in the tree.
        """
        for item, kind in self._item_to_collection.items():
            if kind == collection:
                self.setCurrentItem(item)
                break
