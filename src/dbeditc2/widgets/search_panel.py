# src/dbeditc2/widgets/search_panel.py
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
    - Collection scope selector
    - Semantic field selector

    Emits search intent only.
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

        self._search_edit.textChanged.connect(self.searchTextChanged)
        self._search_edit.returnPressed.connect(
            lambda: self.searchSubmitted.emit(self._search_edit.text())
        )

    def _populate_collections(self) -> None:
        self._collection_combo.clear()
        for kind in CollectionKind:
            self._collection_combo.addItem(kind.name.replace("_", " ").title(), kind)

    def set_collection(self, kind: CollectionKind) -> None:
        """
        Set the current collection scope.
        """
        index = self._collection_combo.findData(kind)
        if index >= 0:
            self._collection_combo.setCurrentIndex(index)

    def set_search_fields(self, fields: list[str]) -> None:
        """
        Populate the semantic field selector.
        """
        self._field_combo.clear()
        for field in fields:
            self._field_combo.addItem(field)

    def clear(self) -> None:
        """
        Clear the search input.
        """
        self._search_edit.clear()
