from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
)

from PySide6.QtCore import Qt

from dbeditc2.widgets.app_toolbar import AppToolBar
from dbeditc2.widgets.navigation_tree import NavigationTree
from dbeditc2.widgets.search_panel import SearchPanel
from dbeditc2.widgets.entry_list_view import EntryListView
from dbeditc2.widgets.entry_details_stack import EntryDetailsStack
from dbeditc2.models import EntrySummary

from sitrepc2.config.paths import gazetteer_path


class MainWindow(QMainWindow):
    """
    DEBUG MODE:
    Search box directly queries location_aliases
    and dumps results into EntryListView.
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("dbeditc2 — DEBUG alias browser")

        # ------------------------------------------------------------
        # Verify DB
        # ------------------------------------------------------------
        self._db_path = gazetteer_path()
        print(f"[DEBUG] gazetteer_path() = {self._db_path}")

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM location_aliases;")
        print(f"[DEBUG] location_aliases row count = {cur.fetchone()[0]}")
        con.close()

        # --- Toolbar (unused here) ---
        self._toolbar = AppToolBar(self)
        self.addToolBar(self._toolbar)

        # --- Core widgets ---
        self._navigation_tree = NavigationTree(self)
        self._search_panel = SearchPanel(self)
        self._entry_list = EntryListView(self)
        self._details_stack = EntryDetailsStack(self)

        # --- Left panel ---
        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._navigation_tree)

        # --- Center panel ---
        center_panel = QWidget(self)
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(self._search_panel)
        center_layout.addWidget(self._entry_list)

        # --- Splitters ---
        splitter = QSplitter(self)
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(self._details_stack)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)

        central = QWidget(self)
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        # ------------------------------------------------------------
        # HARD WIRED DEBUG SEARCH
        # ------------------------------------------------------------
        self._search_panel._search_edit.textChanged.connect(
            self._debug_search_location_aliases
        )

    # ------------------------------------------------------------------
    # DEBUG SEARCH IMPLEMENTATION
    # ------------------------------------------------------------------

    def _debug_search_location_aliases(self, text: str) -> None:
        text = text.strip().lower()

        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        if not text:
            cur.execute(
                """
                SELECT location_id, alias
                FROM location_aliases
                ORDER BY alias
                LIMIT 200
                """
            )
        else:
            cur.execute(
                """
                SELECT location_id, alias
                FROM location_aliases
                WHERE normalized LIKE ?
                ORDER BY alias
                LIMIT 200
                """,
                (f"{text}%",),
            )

        rows = cur.fetchall()
        con.close()

        entries = [
            EntrySummary(
                entry_id=row["location_id"],
                display_name=row["alias"],
                editable=False,
            )
            for row in rows
        ]

        print(f"[DEBUG] displaying {len(entries)} aliases")
        self._entry_list.set_entries(entries)
