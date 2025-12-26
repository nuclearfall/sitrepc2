# src/dbeditc2/widgets/details/empty_state_view.py
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class EmptyStateView(QWidget):
    """
    Placeholder view shown when no entry is selected.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel(
            "Select an entry from the list to view its details,\n"
            "or use the toolbar to add a new one.",
            self,
        )
        label.setAlignment(Qt.AlignCenter)

        layout.addWidget(label)
