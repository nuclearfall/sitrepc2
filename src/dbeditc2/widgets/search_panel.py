from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QLabel,
)

from dbeditc2.enums import CollectionKind


class SearchPanel(QWidget):
    """
    Scoped search panel.

    Provides:
    - Search text field
    - Collection scope selector (display only for now)
    - Semantic field selector (locked to Alias for now)

    Emits:
    - searchTextChanged(str)
    - searchSubmitted(str)
    """

    searchTextChanged = Signal(str)
    searchSubmitted = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Search...")

        self._collection_combo = QComboBox(self)
        self._field_combo = QComboBox(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Search:", self))
        layout.addWidget(self._search_edit, stretch=1)
        layout.addWidget(QLabel("In:", self))
        layout.addWidget(self._collection_combo)
        layout.addWidget(QLabel("By:", self))
        layout.addWidget(self._field_combo)

        self._populate_collections()
        self._populate_fields()

        # --- Signal wiring ---
        self._search_edit.textChanged.connect(
            self.searchTextChanged.emit
        )
        self._search_edit.returnPressed.connect(
            lambda: self.searchSubmitted.emit(self._search_edit.text())
        )

    # ------------------------------------------------------------------

    def _populate_collections(self) -> None:
        """
        Populate collection selector (display-only for now).
        """
        self._collection_combo.clear()
        for kind in CollectionKind:
            self._collection_combo.addItem(
                kind.name.replace("_", " ").title(),
                kind,
            )

        # 🔒 Collection selection is driven elsewhere (NavigationTree)
        self._collection_combo.setEnabled(False)

    def _populate_fields(self) -> None:
        """
       Populate semantic lookup fields.

        For now:
        - Alias is the only supported lookup mode
        - Other modes are shown but disabled
        """
        self._field_combo.clear()
        self._field_combo.addItem("Alias")

        # Future (not yet implemented)
        self._field_combo.addItem("OSM ID")
        self._field_combo.addItem("Wikidata")

        self._field_combo.setCurrentIndex(0)
        self._field_combo.setEnabled(False)

    # ------------------------------------------------------------------

    def set_collection(self, kind: CollectionKind) -> None:
        """
        Set the current collection scope (visual only).
        """
        index = self._collection_combo.findData(kind)
        if index >= 0:
            self._collection_combo.setCurrentIndex(index)

    def clear(self) -> None:
        """
        Clear the search input.
        """
        self._search_edit.clear()
