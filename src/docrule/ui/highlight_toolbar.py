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
    Toolbar for controlling EntityRuler highlight colors.

    Responsibilities:
    - Present a predefined set of highlight colors
    - Show visual swatches for each color
    - Apply color changes to the currently selected ruler

    Signals:
    - colorChanged(ruler_id: str, color_hex: str)
    """

    colorChanged = Signal(str, str)  # ruler_id, color_hex

    # Preconfigured palette (document-editor-style)
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

        self._current_ruler_id: Optional[str] = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setMovable(False)

        self.addWidget(QLabel("Highlight: "))

        self.color_combo = QComboBox(self)
        self.color_combo.setEnabled(False)

        for name, hex_color in self.COLOR_PALETTE.items():
            icon = self._make_color_icon(hex_color)
            self.color_combo.addItem(icon, name, hex_color)

        self.color_combo.currentIndexChanged.connect(
            self._on_color_changed
        )

        self.addWidget(self.color_combo)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_current_ruler(self, ruler_id: Optional[str]) -> None:
        """
        Update the currently selected ruler.

        If no ruler is selected, the toolbar is disabled.
        """
        self._current_ruler_id = ruler_id
        self.color_combo.setEnabled(ruler_id is not None)

    def set_current_color(self, color_hex: str) -> None:
        """
        Sync the dropdown with the ruler's current color.
        """
        for i in range(self.color_combo.count()):
            if self.color_combo.itemData(i) == color_hex:
                self.color_combo.setCurrentIndex(i)
                return

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    def _on_color_changed(self, index: int) -> None:
        if self._current_ruler_id is None:
            return

        color_hex = self.color_combo.itemData(index)
        if not color_hex:
            return

        self.colorChanged.emit(self._current_ruler_id, color_hex)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_color_icon(color_hex: str) -> QIcon:
        """
        Create a small square color swatch icon.
        """
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(color_hex))
        return QIcon(pixmap)
