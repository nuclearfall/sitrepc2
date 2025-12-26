# src/dbeditc2/main_window.py
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
)

from dbeditc2.enums import CollectionKind, EditorMode
from dbeditc2.widgets.app_toolbar import AppToolBar
from dbeditc2.widgets.navigation_tree import NavigationTree
from dbeditc2.widgets.search_panel import SearchPanel
from dbeditc2.widgets.entry_list_view import EntryListView
from dbeditc2.widgets.entry_details_stack import EntryDetailsStack

from sitrepc2.config.paths import gazetteer_path


class MainWindow(QMainWindow):
    """
    Main application window.

    Owns layout and structural wiring only.
    Business logic and state management are delegated elsewhere.
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("dbeditc2")

        # ------------------------------------------------------------
        # HARD DEBUG: verify gazetteer + alias table visibility
        # ------------------------------------------------------------
        db_path = gazetteer_path()
        print(f"[DEBUG] gazetteer_path() = {db_path}")

        try:
            con = sqlite3.connect(db_path)
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM location_aliases;")
            count = cur.fetchone()[0]
            con.close()
        except Exception as e:
            raise RuntimeError(
                "FAILED to read location_aliases from gazetteer.db"
            ) from e

        print(f"[DEBUG] location_aliases row count = {count}")
        # ------------------------------------------------------------

        # --- Toolbar ---
        self._toolbar = AppToolBar(self)
        self.addToolBar(self._toolbar)

        # --- Core widgets ---
        self._navigation_tree = NavigationTree(self)
        self._search_panel = SearchPanel(self)
        self._entry_list = EntryListView(self)
        self._details_stack = EntryDetailsStack(self)

        # --- Left panel (navigation) ---
        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._navigation_tree)

        # --- Center panel (search + list) ---
        center_panel = QWidget(self)
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self._search_panel)
        center_layout.addWidget(self._entry_list)

        # --- Splitters ---
        main_splitter = QSplitter(self)
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(center_panel)
        main_splitter.addWidget(self._details_stack)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 2)

        # --- Central widget ---
        central = QWidget(self)
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(main_splitter)

        self.setCentralWidget(central)

        # --- Structural signal wiring (no logic) ---
        self._navigation_tree.collectionSelected.connect(
            self._on_collection_selected
        )

    # ------------------------------------------------------------------
    # Structural API (no logic)
    # ------------------------------------------------------------------

    def set_collection(self, kind: CollectionKind) -> None:
        self._navigation_tree.set_current(kind)
        self._search_panel.set_collection(kind)

    def set_editor_mode(self, mode: EditorMode) -> None:
        self._toolbar.set_mode(mode)

    def clear_selection(self) -> None:
        self._entry_list.clear()
        self._details_stack.show_empty()

    def show_status_message(self, text: str) -> None:
        self.statusBar().showMessage(text)

    # ------------------------------------------------------------------
    # Temporary placeholder slot
    # ------------------------------------------------------------------

    def _on_collection_selected(self, kind: CollectionKind) -> None:
        """
        Placeholder slot to demonstrate structural connectivity.
        """
        self._details_stack.show_empty()
