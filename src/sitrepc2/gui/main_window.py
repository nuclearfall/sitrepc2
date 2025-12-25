# src/sitrepc2/gui/main_window.py
from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QDockWidget,
    QVBoxLayout,
)

from .controller.document_controller import DocumentController
from .viewer.document_html_viewer import DocumentHtmlViewer
from .ui.highlight_toolbar import HighlightToolBar
from .ui.document_summary_panel import DocumentSummaryPanel
from .ui.attribute_inspector import AttributeInspector
from .ui.gazetteer_alias_panel import (
    GazetteerAliasPanel,
    GazetteerEntityRow,
)
from .ui.ingest_record_picker_dialog import IngestRecordPickerDialog

from sitrepc2.gazetteer.alias_service import (
    search_entities_by_alias,
    load_aliases_for_entities,
    apply_alias_changes,
)


class MainWindow(QMainWindow):
    """
    Main application window.

    Responsibilities:
    - Coordinate controller + viewer
    - Host Gazetteer alias editing panel
    - Apply gazetteer changes and trigger NLP reload
    - Manage entity highlight colors (label -> color)
    """

    # If True: only highlight gazetteer-derived labels.
    # If False: highlight ALL labels in doc.ents (spaCy NER + ruler).
    GAZETTEER_ONLY_HIGHLIGHTING = True

    GAZETTEER_LABELS = {"LOCATION", "REGION", "GROUP", "DIRECTION"}

    DEFAULT_COLORS = [
        "#ffd966",  # Yellow
        "#cfe2f3",  # Light Blue
        "#d9ead3",  # Light Green
        "#f9cb9c",  # Orange
        "#f4cccc",  # Pink
        "#d9d2e9",  # Lavender
        "#eeeeee",  # Gray
    ]

    def __init__(self, *, spacy_model: str, enable_coreferee: bool) -> None:
        super().__init__()

        self.setWindowTitle("spaCy Document Viewer")
        self.resize(1200, 800)

        self.controller = DocumentController(
            spacy_model=spacy_model,
            enable_coreferee=enable_coreferee,
        )

        # Entity label -> color (used by viewer)
        self.ruler_colors: Dict[str, str] = {}

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Central viewer
        self.viewer = DocumentHtmlViewer(self)
        self.setCentralWidget(self.viewer)
        self.viewer.tokenSelected.connect(self._on_token_selected)

        # Left dock: Gazetteer alias panel
        self.alias_panel = GazetteerAliasPanel(self)
        left = QDockWidget("Gazetteer", self)
        left.setWidget(self.alias_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, left)

        self.alias_panel.searchRequested.connect(
            self._on_gazetteer_search_requested
        )
        self.alias_panel.editAliasesRequested.connect(
            self._on_edit_aliases_requested
        )
        self.alias_panel.aliasesCommitted.connect(
            self._on_aliases_committed
        )

        # Right dock: inspection
        self.summary_panel = DocumentSummaryPanel(self)
        self.attr_panel = AttributeInspector(self)

        right_container = QWidget(self)
        right_layout = QVBoxLayout(right_container)
        right_layout.addWidget(self.summary_panel)
        right_layout.addWidget(self.attr_panel)

        right = QDockWidget("Inspection", self)
        right.setWidget(right_container)
        self.addDockWidget(Qt.RightDockWidgetArea, right)

        # Toolbar
        self.toolbar = HighlightToolBar(self)
        self.toolbar.colorChanged.connect(self._on_color_changed)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        load_action = QAction("Load Ingest Text", self)
        load_action.triggered.connect(self._on_load_ingest_text)
        self.toolbar.addAction(load_action)

    # ------------------------------------------------------------------
    # Document lifecycle
    # ------------------------------------------------------------------

    def load_text(self, text: str) -> None:
        doc = self.controller.load_text(text)
        self._ensure_label_colors()
        self.summary_panel.set_doc(doc)
        self._refresh_viewer()

    def _refresh_viewer(self) -> None:
        if not self.controller.doc:
            return

        self.viewer.set_doc(
            self.controller.doc,
            ruler_colors=self.ruler_colors,
        )

    def _ensure_label_colors(self) -> None:
        """
        Ensure every label we intend to highlight has a color.

        Deterministic policy:
        - Determine the set of labels from doc.ents (optionally filtered).
        - Add missing labels in sorted order.
        - Assign colors by cycling DEFAULT_COLORS based on insertion order.
        """
        if not self.controller.doc:
            return

        labels = {ent.label_ for ent in self.controller.doc.ents}

        if self.GAZETTEER_ONLY_HIGHLIGHTING:
            labels = {l for l in labels if l in self.GAZETTEER_LABELS}

        # Add missing labels in stable order
        missing = sorted(l for l in labels if l not in self.ruler_colors)
        for label in missing:
            idx = len(self.ruler_colors) % len(self.DEFAULT_COLORS)
            self.ruler_colors[label] = self.DEFAULT_COLORS[idx]

    # ------------------------------------------------------------------
    # Ingest loading
    # ------------------------------------------------------------------

    def _on_load_ingest_text(self) -> None:
        dialog = IngestRecordPickerDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        texts = dialog.selected_texts()
        if not texts:
            return

        self.load_text("\n\n".join(texts))

    # ------------------------------------------------------------------
    # Gazetteer panel wiring
    # ------------------------------------------------------------------

    def _on_gazetteer_search_requested(
        self,
        domain: str,
        search_text: str,
    ) -> None:
        rows = search_entities_by_alias(
            domain=domain,
            search_text=search_text,
        )

        results = [
            GazetteerEntityRow(
                entity_id=row["entity_id"],
                canonical_name=row["canonical_name"],
                domain=domain,
            )
            for row in rows
        ]

        self.alias_panel.set_results(results)

    def _on_edit_aliases_requested(
        self,
        rows: list[GazetteerEntityRow],
    ) -> None:
        if not rows:
            return

        domain = rows[0].domain
        entity_ids = [r.entity_id for r in rows]

        aliases = load_aliases_for_entities(
            domain=domain,
            entity_ids=entity_ids,
        )

        self.alias_panel.load_aliases(aliases)

    def _on_aliases_committed(
        self,
        domain: str,
        entity_ids: list,
        added: list,
        removed: list,
    ) -> None:
        if not added and not removed:
            return

        apply_alias_changes(
            domain=domain,
            entity_ids=entity_ids,
            added=added,
            removed=removed,
        )

        # Re-derive rulers and rebuild doc
        self.controller.reload_rulers_and_rebuild()
        self._ensure_label_colors()
        self._refresh_viewer()

    # ------------------------------------------------------------------
    # Highlighting
    # ------------------------------------------------------------------

    def _on_color_changed(self, label: str, color: str) -> None:
        if not label:
            return
        self.ruler_colors[label] = color
        self._refresh_viewer()

    # ------------------------------------------------------------------
    # Attribute inspection
    # ------------------------------------------------------------------

    def _on_token_selected(self, token, span) -> None:
        if span:
            label = span.label_

            # Only enable editing if we are actually highlighting this label
            if (
                not self.GAZETTEER_ONLY_HIGHLIGHTING
                or label in self.GAZETTEER_LABELS
            ):
                self.toolbar.set_current_label(label)
                self.toolbar.set_current_color(self.ruler_colors.get(label))
            else:
                self.toolbar.set_current_label(None)

            self.attr_panel.set_span(span)
        else:
            self.toolbar.set_current_label(None)
            self.attr_panel.set_token(token)
