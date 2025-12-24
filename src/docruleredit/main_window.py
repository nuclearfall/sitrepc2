from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QDockWidget,
    QVBoxLayout,
    QInputDialog,
    QMenuBar,
    QMenu,
)

from .controller.document_controller import DocumentController
from .viewer.document_viewer import DocumentViewer
from .ui.entity_ruler_panel import EntityRulerPanel
from .ui.highlight_toolbar import HighlightToolBar
from .ui.document_summary_panel import DocumentSummaryPanel
from .ui.attribute_inspector import AttributeInspector
from .ui.menus import MenuActions
from .io.ruler_io import load_rulers_jsonl, save_rulers_jsonl
from .models.entity_ruler import EntityRulerModel


class MainWindow(QMainWindow):
    """
    Fully wired main window.

    Owns:
    - Controller
    - Viewer
    - Docks
    - Toolbar
    - Menu actions
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("spaCy Document Viewer")
        self.resize(1200, 800)

        self.controller = DocumentController()
        self.rulers: Dict[str, EntityRulerModel] = {}

        # IMPORTANT: menus must exist before MenuActions wiring
        self._build_menu_bar()
        self._build_ui()

        self.menus = MenuActions(self)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        # ---- File menu ----
        file_menu = QMenu("&File", self)

        self.open_text_action = QAction("Open Text File", self)
        self.open_json_action = QAction("Open JSON / JSONL File", self)
        self.open_csv_action = QAction("Open CSV File", self)

        file_menu.addAction(self.open_text_action)
        file_menu.addAction(self.open_json_action)
        file_menu.addAction(self.open_csv_action)

        file_menu.addSeparator()

        self.open_rulers_action = QAction("Open Rulers", self)
        self.save_rulers_action = QAction("Save Current Rulers", self)

        file_menu.addAction(self.open_rulers_action)
        file_menu.addAction(self.save_rulers_action)

        # ---- Edit menu ----
        edit_menu = QMenu("&Edit", self)

        self.copy_action = QAction("Copy", self)
        self.cut_action = QAction("Cut", self)
        self.paste_action = QAction("Paste", self)

        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.paste_action)

        menu_bar.addMenu(file_menu)
        menu_bar.addMenu(edit_menu)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # ---- Central viewer ----
        self.viewer = DocumentViewer(self)
        self.setCentralWidget(self.viewer)
        self.viewer.tokenSelected.connect(self._on_token_selected)

        # ---- Left dock: Entity rulers ----
        self.ruler_panel = EntityRulerPanel(self)
        self.ruler_panel.rulerAdded.connect(self._on_ruler_added)
        self.ruler_panel.rulerRemoved.connect(self._on_ruler_removed)
        self.ruler_panel.rulerSelected.connect(self._on_ruler_selected)

        left_dock = QDockWidget("Entity Rulers", self)
        left_dock.setWidget(self.ruler_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, left_dock)

        # ---- Right dock: Inspection ----
        self.summary_panel = DocumentSummaryPanel(self)
        self.attr_panel = AttributeInspector(self)

        right_container = QWidget(self)
        right_layout = QVBoxLayout(right_container)
        right_layout.addWidget(self.summary_panel)
        right_layout.addWidget(self.attr_panel)

        right_dock = QDockWidget("Inspection", self)
        right_dock.setWidget(right_container)
        self.addDockWidget(Qt.RightDockWidgetArea, right_dock)

        # ---- Toolbar ----
        self.toolbar = HighlightToolBar(self)
        self.toolbar.colorChanged.connect(self._on_color_changed)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

    # ------------------------------------------------------------------
    # Document loading
    # ------------------------------------------------------------------

    def load_text(self, text: str) -> None:
        doc = self.controller.load_text(text)
        self._refresh_viewer()
        self.summary_panel.set_doc(doc)

    def load_text_from_external(self, text: str) -> None:
        self.load_text(text)

    def load_file_from_external(self, path: str) -> None:
        # Delegate to menu logic (keeps one code path)
        self.menus._open_text()

    # ------------------------------------------------------------------
    # Viewer refresh
    # ------------------------------------------------------------------

    def _refresh_viewer(self) -> None:
        color_map = {r.label: r.color for r in self.rulers.values()}
        self.viewer.set_doc(self.controller.doc, ruler_colors=color_map)

    # ------------------------------------------------------------------
    # Ruler handling
    # ------------------------------------------------------------------

    def _on_ruler_added(self, ruler: EntityRulerModel) -> None:
        self.rulers[ruler.ruler_id] = ruler

        spacy_ruler = self.controller.get_user_entity_ruler()
        patterns = [
            {"label": ruler.label, "pattern": p}
            for p in ruler.iter_patterns()
        ]
        spacy_ruler.add_patterns(patterns)

        self.controller.rebuild_doc()
        self._refresh_viewer()

    def _on_ruler_removed(self, ruler_id: str) -> None:
        self.rulers.pop(ruler_id, None)
        self.controller.reset_user_entity_ruler()

        for ruler in self.rulers.values():
            self._on_ruler_added(ruler)

    def _on_ruler_selected(self, ruler_id: Optional[str]) -> None:
        self.toolbar.set_current_ruler(ruler_id)
        if ruler_id and ruler_id in self.rulers:
            self.toolbar.set_current_color(self.rulers[ruler_id].color)

    def _on_color_changed(self, ruler_id: str, color: str) -> None:
        if ruler_id in self.rulers:
            self.rulers[ruler_id].color = color
            self._refresh_viewer()

    # ------------------------------------------------------------------
    # Attribute inspection
    # ------------------------------------------------------------------

    def _on_token_selected(self, token, span) -> None:
        if span is not None:
            self.attr_panel.set_span(span)
        else:
            self.attr_panel.set_token(token)

    # ------------------------------------------------------------------
    # Ruler persistence
    # ------------------------------------------------------------------

    def load_rulers(self) -> None:
        path, _ = QInputDialog.getText(
            self, "Open Rulers", "Path to JSONL file:"
        )
        if not path:
            return

        rulers = load_rulers_jsonl(Path(path))
        self.rulers = {r.ruler_id: r for r in rulers}

        self.controller.reset_user_entity_ruler()
        for ruler in rulers:
            self._on_ruler_added(ruler)

    def save_rulers(self) -> None:
        path, _ = QInputDialog.getText(
            self, "Save Rulers", "Path to JSONL file:"
        )
        if not path:
            return

        save_rulers_jsonl(Path(path), self.rulers.values())

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def prompt_text(self, title: str, label: str):
        return QInputDialog.getText(self, title, label)
