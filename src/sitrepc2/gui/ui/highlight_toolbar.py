# src/sitrepc2/gui/ui/highlight_toolbar.py
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QIcon
from PySide6.QtWidgets import (
    QToolBar,
    QLabel,
    QComboBox,
)


class HighlightToolBar(QToolBar):
    """
    Toolbar for editing highlight colors of entity labels.

    Responsibilities:
    - Allow user to change color for the *currently selected* label
    - Emit colorChanged(label, color_hex)

    Does NOT:
    - Track all labels
    - Assign default colors
    """

    colorChanged = Signal(str, str)  # label, color_hex

    COLOR_PALETTE: Dict[str, str] = {
        "Yellow": "#ffd966",
        "Light Blue": "#cfe2f3",
        "Light Green": "#d9ead3",
        "Orange": "#f9cb9c",
        "Pink": "#f4cccc",
        "Lavender": "#d9d2e9",
        "Gray": "#eeeeee",
    }

    def __init__(self, parent=None) -> None:
        super().__init__("Highlight Controls", parent)

        self._current_label: Optional[str] = None
        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setMovable(False)

        self.addWidget(QLabel("Highlight: "))

        self.color_combo = QComboBox(self)
        self.color_combo.setEnabled(False)

        for name, hex_color in self.COLOR_PALETTE.items():
            self.color_combo.addItem(
                self._make_color_icon(hex_color),
                name,
                hex_color,
            )

        self.color_combo.currentIndexChanged.connect(
            self._on_color_changed
        )

        self.addWidget(self.color_combo)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_current_label(self, label: Optional[str]) -> None:
        """
        Set the label currently being edited.
        """
        self._current_label = label
        self.color_combo.setEnabled(label is not None)

    def set_current_color(self, color_hex: Optional[str]) -> None:
        """
        Sync dropdown to current label color.
        """
        if not color_hex:
            return

        for i in range(self.color_combo.count()):
            if self.color_combo.itemData(i) == color_hex:
                self.color_combo.setCurrentIndex(i)
                break

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_color_changed(self, index: int) -> None:
        if not self._current_label:
            return

        color_hex = self.color_combo.itemData(index)
        if not color_hex:
            return

        self.colorChanged.emit(self._current_label, color_hex)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_color_icon(color_hex: str) -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(color_hex))
        return QIcon(pixmap)
