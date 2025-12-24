from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
)

from ..models.entity_ruler import EntityRulerModel


class EntityRulerPanel(QWidget):
    """
    Left-dock panel for creating and managing user EntityRulers.

    Responsibilities:
    - Collect ruler name, label, patterns
    - Toggle normalization
    - Add/remove rulers
    - Present active rulers list
    - Emit intent signals (no spaCy calls here)

    Signals:
    - rulerAdded(EntityRulerModel)
    - rulerRemoved(ruler_id: str)
    - rulerSelected(ruler_id: str | None)
    """

    rulerAdded = Signal(object)      # EntityRulerModel
    rulerRemoved = Signal(str)       # ruler_id
    rulerSelected = Signal(object)   # ruler_id | None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ---- Ruler Name ----
        layout.addWidget(QLabel("Ruler Name"))
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("Human-readable ruler name")
        layout.addWidget(self.name_edit)

        # ---- Entity Label ----
        layout.addWidget(QLabel("Entity Label (ent_type)"))
        self.label_edit = QLineEdit(self)
        self.label_edit.setPlaceholderText("e.g. UNIT, LOCATION, CODEWORD")
        layout.addWidget(self.label_edit)

        # ---- Patterns ----
        layout.addWidget(QLabel("Patterns (comma, semicolon, or newline separated)"))
        self.patterns_edit = QTextEdit(self)
        self.patterns_edit.setPlaceholderText(
            "alpha\nbravo; charlie, delta"
        )
        layout.addWidget(self.patterns_edit)

        # ---- Normalization ----
        self.normalize_checkbox = QCheckBox("Normalize patterns using .lower()", self)
        self.normalize_checkbox.setChecked(True)
        layout.addWidget(self.normalize_checkbox)

        # ---- Buttons ----
        button_row = QHBoxLayout()
        self.add_button = QPushButton("Add Entity Ruler", self)
        self.remove_button = QPushButton("Remove Entity Ruler", self)
        self.remove_button.setEnabled(False)

        button_row.addWidget(self.add_button)
        button_row.addWidget(self.remove_button)
        layout.addLayout(button_row)

        # ---- Ruler List ----
        layout.addWidget(QLabel("Active Entity Rulers"))
        self.ruler_list = QListWidget(self)
        layout.addWidget(self.ruler_list)

        layout.addStretch()

        # ---- Wiring ----
        self.add_button.clicked.connect(self._on_add_clicked)
        self.remove_button.clicked.connect(self._on_remove_clicked)
        self.ruler_list.currentItemChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    def _on_add_clicked(self) -> None:
        name = self.name_edit.text().strip()
        label = self.label_edit.text().strip()
        patterns = self._parse_patterns(self.patterns_edit.toPlainText())
        normalize = self.normalize_checkbox.isChecked()

        if not name or not label or not patterns:
            # Validation intentionally minimal; UI layer may add dialogs later
            return

        ruler = EntityRulerModel(
            name=name,
            label=label,
            patterns=patterns,
            normalize=normalize,
        )

        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, ruler.ruler_id)
        self.ruler_list.addItem(item)
        self.ruler_list.setCurrentItem(item)

        self.rulerAdded.emit(ruler)

        # Reset editor fields for convenience
        self.name_edit.clear()
        self.label_edit.clear()
        self.patterns_edit.clear()
        self.normalize_checkbox.setChecked(True)

    def _on_remove_clicked(self) -> None:
        item = self.ruler_list.currentItem()
        if not item:
            return

        ruler_id = item.data(Qt.UserRole)
        row = self.ruler_list.row(item)
        self.ruler_list.takeItem(row)

        self.remove_button.setEnabled(False)
        self.rulerRemoved.emit(ruler_id)

    def _on_selection_changed(
        self,
        current: Optional[QListWidgetItem],
        previous: Optional[QListWidgetItem],
    ) -> None:
        if current:
            self.remove_button.setEnabled(True)
            self.rulerSelected.emit(current.data(Qt.UserRole))
        else:
            self.remove_button.setEnabled(False)
            self.rulerSelected.emit(None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_patterns(text: str) -> List[str]:
        """
        Split user input into individual patterns.

        Separators:
        - comma
        - semicolon
        - newline
        """
        raw = (
            text.replace(",", "\n")
            .replace(";", "\n")
            .splitlines()
        )
        return [p.strip() for p in raw if p.strip()]
