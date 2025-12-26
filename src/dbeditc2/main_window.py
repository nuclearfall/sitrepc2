# src/sitrepc2/gui/main_window.py
from __future__ import annotations

from typing import Dict, Optional, Sequence

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

        # Pending alias text built from viewer selection (non-entity tokens)
        self._pending_alias_text: Optional[str] = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Central viewer
        self.viewer = DocumentHtmlViewer(self)
        self.setCentralWidget(self.viewer)

        # Token click selection (existing)
        self.viewer.tokenSelected.connect(self._on_token_selected)

        # Multi-token selection (NEW canonical hook)
        # DocumentHtmlViewer emits list[Token]
        if hasattr(self.viewer, "tokensSelected"):
            self.viewer.tokensSelected.connect(self._on_viewer_tokens_selected)

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

        # These are part of your current panel contract (as used by your file)
        # - selectionChanged: list[GazetteerEntityRow]
        # - addAliasRequested: str
        if hasattr(self.alias_panel, "selectionChanged"):
            self.alias_panel.selectionChanged.connect(self._on_gazetteer_selection_changed)
        if hasattr(self.alias_panel, "addAliasRequested"):
            self.alias_panel.addAliasRequested.connect(self._on_add_alias_requested)

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

        # Clear any previous pending alias selection after load
        self._pending_alias_text = None
        self._push_pending_alias_to_panel()

    def _refresh_viewer(self) -> None:
        if not self.controller.doc:
            return

        self.viewer.set_doc(
            self.controller.doc,
            ruler_colors=self.ruler_colors,
        )

    def _ensure_label_colors(self) -> None:
        if not self.controller.doc:
            return

        labels = {ent.label_ for ent in self.controller.doc.ents}

        if self.GAZETTEER_ONLY_HIGHLIGHTING:
            labels = {l for l in labels if l in self.GAZETTEER_LABELS}

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
        self._push_pending_alias_to_panel()

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

        self.controller.reload_rulers_and_rebuild()
        self._ensure_label_colors()
        self._refresh_viewer()

        # After commit, keep pending alias available (user may add more)
        self._push_pending_alias_to_panel()

    # ------------------------------------------------------------------
    # Viewer -> pending alias (multi-token selection)
    # ------------------------------------------------------------------

    def _on_viewer_tokens_selected(self, tokens: Sequence) -> None:
        """
        Viewer emits list[Token] for non-entity selections.
        We turn that into a single alias string (space-normalized).
        """
        if not tokens:
            self._pending_alias_text = None
            self._push_pending_alias_to_panel()
            return

        # Build the exact displayed text as closely as possible
        # while still normalizing to a single alias string.
        # Use text_with_ws to preserve intended spacing, then normalize.
        raw = "".join(getattr(t, "text_with_ws", f"{t.text} ") for t in tokens).strip()
        alias = " ".join(raw.split())  # normalize internal whitespace

        self._pending_alias_text = alias or None
        self._push_pending_alias_to_panel()

    def _push_pending_alias_to_panel(self) -> None:
        """
        Keep the panel’s CTA state up to date based on:
        - pending alias text (from viewer)
        - current gazetteer selection (panel-side)
        """
        if hasattr(self.alias_panel, "set_pending_alias"):
            self.alias_panel.set_pending_alias(self._pending_alias_text)

    def _on_gazetteer_selection_changed(self, rows) -> None:
        # Selection changed affects whether the "Add Alias..." CTA should be enabled
        self._push_pending_alias_to_panel()

    def _on_add_alias_requested(self, alias_text: str) -> None:
        """
        Panel asks to apply the alias_text to currently selected gazetteer entities.
        Backend behavior remains identical (apply_alias_changes).
        """
        alias_text = (alias_text or "").strip()
        if not alias_text:
            return

        # Prefer a public accessor if your panel provides one
        rows = None
        if hasattr(self.alias_panel, "selected_rows"):
            rows = self.alias_panel.selected_rows()
        elif hasattr(self.alias_panel, "get_selected_rows"):
            rows = self.alias_panel.get_selected_rows()
        else:
            # Fallback to your current internal field (avoids breaking today)
            rows = getattr(self.alias_panel, "_selected_rows", None)

        if not rows:
            return

        domain = rows[0].domain
        entity_ids = [r.entity_id for r in rows]

        apply_alias_changes(
            domain=domain,
            entity_ids=entity_ids,
            added=[alias_text],
            removed=[],
        )

        self.controller.reload_rulers_and_rebuild()
        self._ensure_label_colors()
        self._refresh_viewer()

        # keep the alias available for quick repeat adds
        self._push_pending_alias_to_panel()

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
