from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)

from PySide6.QtCore import Qt

from sitrepc2.config.paths import gazetteer_path


class MainWindow(QMainWindow):
    """
    Minimal alias → location viewer.

    - Left: location_aliases (LIMIT 200)
    - Right: locations row for selected location_id
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("dbeditc2 — alias → location debug")

        self._db_path = gazetteer_path()
        print(f"[DEBUG] gazetteer_path = {self._db_path}")

        # --------------------------------------------------
        # Widgets
        # --------------------------------------------------

        self._alias_list = QListWidget(self)
        self._alias_list.itemClicked.connect(self._on_alias_clicked)

        self._details_widget = QWidget(self)
        self._details_layout = QVBoxLayout(self._details_widget)
        self._details_layout.setAlignment(Qt.AlignTop)

        self._detail_labels: dict[str, QLabel] = {}
        for field in ("location_id", "name", "lat", "lon", "place", "wikidata"):
            lbl = QLabel("-", self)
            self._detail_labels[field] = lbl
            self._details_layout.addWidget(lbl)

        # --------------------------------------------------
        # Layout
        # --------------------------------------------------

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.addWidget(self._alias_list, stretch=1)
        layout.addWidget(self._details_widget, stretch=1)

        self.setCentralWidget(central)

        # --------------------------------------------------
        # Load initial data
        # --------------------------------------------------

        self._load_aliases()

    # ------------------------------------------------------
    # Data loading
    # ------------------------------------------------------

    def _load_aliases(self) -> None:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        cur.execute(
            """
            SELECT location_id, alias
            FROM location_aliases
            ORDER BY alias
            LIMIT 200;
            """
        )

        rows = cur.fetchall()
        con.close()

        print(f"[DEBUG] loaded {len(rows)} aliases")

        self._alias_list.clear()
        for row in rows:
            text = row["alias"]
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, row["location_id"])
            self._alias_list.addItem(item)

    # ------------------------------------------------------
    # Interaction
    # ------------------------------------------------------

    def _on_alias_clicked(self, item: QListWidgetItem) -> None:
        location_id = item.data(Qt.UserRole)
        print(f"[DEBUG] alias clicked → location_id={location_id}")

        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        cur.execute(
            """
            SELECT location_id, name, lat, lon, place, wikidata
            FROM locations
            WHERE location_id = ?;
            """,
            (location_id,),
        )

        row = cur.fetchone()
        con.close()

        if row is None:
            self._show_message("Location not found")
            return

        self._update_details(row)

    # ------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------

    def _update_details(self, row: sqlite3.Row) -> None:
        self._detail_labels["location_id"].setText(
            f"location_id: {row['location_id']}"
        )
        self._detail_labels["name"].setText(f"name: {row['name']}")
        self._detail_labels["lat"].setText(f"lat: {row['lat']}")
        self._detail_labels["lon"].setText(f"lon: {row['lon']}")
        self._detail_labels["place"].setText(f"place: {row['place']}")
        self._detail_labels["wikidata"].setText(f"wikidata: {row['wikidata']}")

    def _show_message(self, text: str) -> None:
        for lbl in self._detail_labels.values():
            lbl.setText(text)

# from __future__ import annotations

# import sqlite3

# from PySide6.QtWidgets import (
#     QMainWindow,
#     QWidget,
#     QVBoxLayout,
#     QHBoxLayout,
#     QSplitter,
# )

# from PySide6.QtCore import Qt

# from dbeditc2.widgets.app_toolbar import AppToolBar
# from dbeditc2.widgets.navigation_tree import NavigationTree
# from dbeditc2.widgets.search_panel import SearchPanel
# from dbeditc2.widgets.entry_list_view import EntryListView
# from dbeditc2.widgets.entry_details_stack import EntryDetailsStack
# from dbeditc2.models import EntrySummary

# from sitrepc2.config.paths import gazetteer_path


# class MainWindow(QMainWindow):
#     """
#     DEBUG MODE:
#     Search box directly queries location_aliases
#     and dumps results into EntryListView.
#     """

#     def __init__(self) -> None:
#         super().__init__()

#         self.setWindowTitle("dbeditc2 — DEBUG alias browser")

#         # ------------------------------------------------------------
#         # Verify DB
#         # ------------------------------------------------------------
#         self._db_path = gazetteer_path()
#         print(f"[DEBUG] gazetteer_path() = {self._db_path}")

#         con = sqlite3.connect(self._db_path)
#         cur = con.cursor()
#         cur.execute("SELECT COUNT(*) FROM location_aliases;")
#         print(f"[DEBUG] location_aliases row count = {cur.fetchone()[0]}")
#         con.close()

#         # --- Toolbar (unused here) ---
#         self._toolbar = AppToolBar(self)
#         self.addToolBar(self._toolbar)

#         # --- Core widgets ---
#         self._navigation_tree = NavigationTree(self)
#         self._search_panel = SearchPanel(self)
#         self._entry_list = EntryListView(self)
#         self._details_stack = EntryDetailsStack(self)

#         # --- Left panel ---
#         left_panel = QWidget(self)
#         left_layout = QVBoxLayout(left_panel)
#         left_layout.setContentsMargins(0, 0, 0, 0)
#         left_layout.addWidget(self._navigation_tree)

#         # --- Center panel ---
#         center_panel = QWidget(self)
#         center_layout = QVBoxLayout(center_panel)
#         center_layout.setContentsMargins(0, 0, 0, 0)
#         center_layout.addWidget(self._search_panel)
#         center_layout.addWidget(self._entry_list)

#         # --- Splitters ---
#         splitter = QSplitter(self)
#         splitter.addWidget(left_panel)
#         splitter.addWidget(center_panel)
#         splitter.addWidget(self._details_stack)
#         splitter.setStretchFactor(1, 1)
#         splitter.setStretchFactor(2, 2)

#         central = QWidget(self)
#         central_layout = QHBoxLayout(central)
#         central_layout.setContentsMargins(0, 0, 0, 0)
#         central_layout.addWidget(splitter)
#         self.setCentralWidget(central)

#         # ------------------------------------------------------------
#         # HARD WIRED DEBUG SEARCH
#         # ------------------------------------------------------------
#         self._search_panel._search_edit.textChanged.connect(
#             self._debug_search_location_aliases
#         )

#     # ------------------------------------------------------------------
#     # DEBUG SEARCH IMPLEMENTATION
#     # ------------------------------------------------------------------

#     def _debug_search_location_aliases(self, text: str) -> None:
#         text = text.strip().lower()

#         con = sqlite3.connect(self._db_path)
#         con.row_factory = sqlite3.Row
#         cur = con.cursor()

#         if not text:
#             cur.execute(
#                 """
#                 SELECT location_id, alias
#                 FROM location_aliases
#                 ORDER BY alias
#                 LIMIT 200
#                 """
#             )
#         else:
#             cur.execute(
#                 """
#                 SELECT location_id, alias
#                 FROM location_aliases
#                 WHERE normalized LIKE ?
#                 ORDER BY alias
#                 LIMIT 200
#                 """,
#                 (f"{text}%",),
#             )

#         rows = cur.fetchall()
#         con.close()

#         entries = [
#             EntrySummary(
#                 entry_id=row["location_id"],
#                 display_name=row["alias"],
#                 editable=False,
#             )
#             for row in rows
#         ]

#         print(f"[DEBUG] displaying {len(entries)} aliases")
#         self._entry_list.set_entries(entries)
