# gui/ui/gazetteer_alias_panel.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QTextEdit,
    QScrollArea,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QAbstractItemView,
)


# ---------------------------------------------------------------------
# UI data model
# ---------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GazetteerEntityRow:
    """
    Minimal canonical entity representation for UI use only.
    """
    entity_id: int | str
    canonical_name: str
    domain: str  # LOCATION / REGION / GROUP / DIRECTION


# ---------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------

class GazetteerAliasPanel(QWidget):
    """
    UI panel for searching gazetteer entities by alias and
    editing aliases in bulk.

    UI-only:
    - No DB access
    - No NLP access
    - Emits structured intent signals only
    """

    # ------------------------------
    # Signals
    # ------------------------------

    domainChanged = Signal(str)                    # domain
    searchRequested = Signal(str, str)             # domain, search_text
    selectionChanged = Signal(list)                # list[GazetteerEntityRow]
    editAliasesRequested = Signal(list)            # list[GazetteerEntityRow]

    aliasesCommitted = Signal(
        str,                                      # domain
        list,                                     # entity_ids
        list,                                     # added_aliases
        list,                                     # removed_aliases
    )
    addAliasRequested = Signal(str)

    # ------------------------------------------------------------------

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # ---------------------------
        # Internal state
        # ---------------------------

        self._current_domain: str = "LOCATION"
        self._results: List[GazetteerEntityRow] = []
        self._selected_rows: List[GazetteerEntityRow] = []

        self._original_aliases: Set[str] = set()
        self._current_aliases: Set[str] = set()
        self._alias_editor_visible: bool = False
        self._pending_alias_text: str = ""
        # ---------------------------
        # Build UI
        # ---------------------------

        self._build_ui()
        self._wire_signals()

        # ---------------------------
        # Search debounce timer
        # ---------------------------

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(
            self._on_search_timer_fired
        )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        outer_layout.addWidget(self.scroll_area)

        self._content = QWidget()
        self.scroll_area.setWidget(self._content)

        layout = QVBoxLayout(self._content)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # --------------------------------------------------
        # Domain selector
        # --------------------------------------------------

        domain_layout = QHBoxLayout()
        domain_label = QLabel("Gazetteer:")
        self.domain_combo = QComboBox()
        self.domain_combo.addItems(
            ["LOCATION", "REGION", "GROUP", "DIRECTION"]
        )

        domain_layout.addWidget(domain_label)
        domain_layout.addWidget(self.domain_combo)
        layout.addLayout(domain_layout)

        # --------------------------------------------------
        # Search field
        # --------------------------------------------------

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Search by alias (any name, any language)…"
        )
        layout.addWidget(self.search_edit)

        self.status_label = QLabel()
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet(
            "color: #888; font-style: italic;"
        )
        layout.addWidget(self.status_label)

        # --------------------------------------------------
        # Results list
        # --------------------------------------------------

        self.results_list = QListWidget()
        self.results_list.setSelectionMode(
            QAbstractItemView.ExtendedSelection
        )
        self.results_list.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        layout.addWidget(self.results_list)

        # --------------------------------------------------
        # Alias editing
        # --------------------------------------------------

        self.add_alias_btn = QPushButton("Add Alias from Selection")
        self.add_alias_btn.setVisible(False)
        layout.addWidget(self.add_alias_btn)

        self.edit_aliases_btn = QPushButton("Edit Aliases…")
        self.edit_aliases_btn.setEnabled(False)
        layout.addWidget(self.edit_aliases_btn)

        self.alias_editor = QTextEdit()
        self.alias_editor.setPlaceholderText(
            "One alias per line.\n"
            "Aliases will apply to ALL selected entries."
        )
        self.alias_editor.setVisible(False)
        self.alias_editor.setMinimumHeight(120)
        layout.addWidget(self.alias_editor)

        btn_layout = QHBoxLayout()
        self.alias_apply_btn = QPushButton("Apply")
        self.alias_cancel_btn = QPushButton("Cancel")
        self.alias_apply_btn.setEnabled(False)

        btn_layout.addStretch(1)
        btn_layout.addWidget(self.alias_apply_btn)
        btn_layout.addWidget(self.alias_cancel_btn)

        self._alias_btn_container = QWidget()
        self._alias_btn_container.setLayout(btn_layout)
        self._alias_btn_container.setVisible(False)
        layout.addWidget(self._alias_btn_container)

        layout.addStretch(1)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _wire_signals(self) -> None:
        self.domain_combo.currentTextChanged.connect(
            self._on_domain_changed
        )
        self.search_edit.textChanged.connect(
            self._on_search_text_changed
        )
        self.search_edit.returnPressed.connect(
            self._on_search_requested_immediate
        )
        self.results_list.itemSelectionChanged.connect(
            self._on_selection_changed
        )
        self.edit_aliases_btn.clicked.connect(
            self._on_edit_aliases_clicked
        )
        self.alias_editor.textChanged.connect(
            self._on_alias_text_changed
        )
        self.alias_apply_btn.clicked.connect(
            self._on_alias_apply_clicked
        )
        self.alias_cancel_btn.clicked.connect(
            self._on_alias_cancel_clicked
        )
        self.add_alias_btn.clicked.connect(
            self._on_add_alias_clicked
        )


    # ------------------------------------------------------------------
    # Domain & search handling
    # ------------------------------------------------------------------

    def _on_domain_changed(self, domain: str) -> None:
        self._current_domain = domain
        self._search_timer.stop()
        self.search_edit.clear()
        self.clear_results()
        self.domainChanged.emit(domain)

    def _on_search_text_changed(self, text: str) -> None:
        text = text.strip()

        if not text:
            self.clear_results()
            self._search_timer.stop()
            return

        self.edit_aliases_btn.setEnabled(False)
        self._search_timer.stop()
        self._search_timer.start()

    def _on_search_timer_fired(self) -> None:
        text = self.search_edit.text().strip()
        if not text:
            return

        self.status_label.setText("Searching…")
        self.status_label.setVisible(True)

        self.searchRequested.emit(self._current_domain, text)

    def _on_search_requested_immediate(self) -> None:
        self._search_timer.stop()

        text = self.search_edit.text().strip()
        if not text:
            return

        self.status_label.setText("Searching…")
        self.status_label.setVisible(True)
        self.edit_aliases_btn.setEnabled(False)

        self.searchRequested.emit(self._current_domain, text)

    # ------------------------------------------------------------------
    # Results & selection
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        if self._alias_editor_visible:
            return

        rows: List[GazetteerEntityRow] = []
        for item in self.results_list.selectedItems():
            row = item.data(Qt.UserRole)
            if isinstance(row, GazetteerEntityRow):
                rows.append(row)

        canonical_names = {r.canonical_name for r in rows}
        if len(canonical_names) > 1:
            self.results_list.blockSignals(True)
            self.results_list.clearSelection()
            self.results_list.blockSignals(False)
            return

        self._selected_rows = rows
        self.edit_aliases_btn.setEnabled(bool(rows))
        self.selectionChanged.emit(rows)

    # ------------------------------------------------------------------
    # Alias editor lifecycle
    # ------------------------------------------------------------------

    def _on_edit_aliases_clicked(self) -> None:
        if not self._selected_rows:
            return

        self._alias_editor_visible = True
        self.results_list.setEnabled(False)
        self.edit_aliases_btn.setEnabled(False)

        self.alias_editor.setVisible(True)
        self._alias_btn_container.setVisible(True)
        self.alias_editor.setPlainText(
            "\n".join(sorted(self._original_aliases))
        )
        self.alias_apply_btn.setEnabled(False)

        self.editAliasesRequested.emit(self._selected_rows)

    def _on_alias_text_changed(self) -> None:
        current = {
            line.strip()
            for line in self.alias_editor.toPlainText().splitlines()
            if line.strip()
        }

        self._current_aliases = current
        self.alias_apply_btn.setEnabled(
            current != self._original_aliases
        )

    def _on_alias_apply_clicked(self) -> None:
        added = sorted(self._current_aliases - self._original_aliases)
        removed = sorted(self._original_aliases - self._current_aliases)

        if not (added or removed):
            return

        entity_ids = [r.entity_id for r in self._selected_rows]

        self.aliasesCommitted.emit(
            self._current_domain,
            entity_ids,
            added,
            removed,
        )

        self._collapse_alias_editor()

    def _on_alias_cancel_clicked(self) -> None:
        self._collapse_alias_editor()

    def _collapse_alias_editor(self) -> None:
        self.alias_editor.clear()
        self.alias_editor.setVisible(False)
        self._alias_btn_container.setVisible(False)

        self.results_list.setEnabled(True)

        self._alias_editor_visible = False
        self._original_aliases.clear()
        self._current_aliases.clear()

    def _on_add_alias_clicked(self) -> None:
        if self._pending_alias_text:
            self.addAliasRequested.emit(self._pending_alias_text)
            
    # ------------------------------------------------------------------
    # Public UI API
    # ------------------------------------------------------------------

    def set_results(self, rows: List[GazetteerEntityRow]) -> None:
        self.results_list.clear()
        self._results = rows
        self._selected_rows.clear()
        self.edit_aliases_btn.setEnabled(False)

        if not rows:
            self.status_label.setText("No results found")
            self.status_label.setVisible(True)
            return

        self.status_label.setVisible(False)

        for row in rows:
            item = QListWidgetItem(row.canonical_name)
            item.setData(Qt.UserRole, row)
            self.results_list.addItem(item)

    def clear_results(self) -> None:
        self.results_list.clear()
        self._results.clear()
        self._selected_rows.clear()
        self.status_label.setVisible(False)
        self.edit_aliases_btn.setEnabled(False)

    def load_aliases(self, aliases: List[str]) -> None:
        self._original_aliases = set(aliases)
        self._current_aliases = set(aliases)

        if self._alias_editor_visible:
            self.alias_editor.setPlainText(
                "\n".join(sorted(aliases))
            )

    def set_pending_alias(self, text: Optional[str]) -> None:
        self._pending_alias_text = text.strip() if text else None
        self.add_alias_btn.setVisible(
            bool(self._pending_alias_text and self._selected_rows)
        )

