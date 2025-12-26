# src/dbeditc2/widgets/entry_list_view.py
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from dbeditc2.models import EntrySummary


class EntryListView(QListWidget):
    """
    Read-only list of entries for the selected collection.

    Displays semantic summaries and emits selection intent.
    """

    entrySelected = Signal(Any)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setSelectionMode(QListWidget.SingleSelection)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def set_entries(self, entries: list[EntrySummary]) -> None:
        """
        Populate the list with entry summaries.
        """
        self.clear()

        for entry in entries:
            item = QListWidgetItem(entry.display_name)
            item.setData(Qt.UserRole, entry.entry_id)

            if entry.subtitle:
                item.setToolTip(entry.subtitle)

            if not entry.editable:
                font = item.font()
                font.setItalic(True)
                item.setFont(font)

            self.addItem(item)

    def set_selection(self, entry_id: Any) -> None:
        """
        Programmatically select an entry by ID.
        """
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.UserRole) == entry_id:
                self.setCurrentItem(item)
                break

    def clear(self) -> None:
        """
        Clear all entries.
        """
        super().clear()

    def _on_selection_changed(self) -> None:
        items = self.selectedItems()
        if not items:
            return

        entry_id = items[0].data(Qt.UserRole)
        self.entrySelected.emit(entry_id)
