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
    QLineEdit,
    QComboBox,
)

from PySide6.QtCore import Qt

from sitrepc2.config.paths import gazetteer_path


class MainWindow(QMainWindow):
    """
    Alias / osm_id / wikidata → location viewer.

    - Search bar
    - Lookup mode selector
    - Alias results list
    - Location details
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("dbeditc2 — alias / id lookup")

        self._db_path = gazetteer_path()
        print(f"[DEBUG] gazetteer_path = {self._db_path}")

        # --------------------------------------------------
        # Widgets
        # --------------------------------------------------

        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Search…")
        self._search_edit.textChanged.connect(self._on_search_changed)

        self._lookup_mode = QComboBox(self)
        self._lookup_mode.addItems(["alias", "wikidata"])
        self._lookup_mode.setCurrentText("alias")
        self._lookup_mode.currentTextChanged.connect(
            lambda _: self._on_search_changed(self._search_edit.text())
        )

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

        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self._search_edit)
        left_layout.addWidget(self._lookup_mode)
        left_layout.addWidget(self._alias_list)

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.addWidget(left_panel, stretch=1)
        layout.addWidget(self._details_widget, stretch=1)

        self.setCentralWidget(central)

        # --------------------------------------------------
        # Initial load
        # --------------------------------------------------

        self._load_by_alias(search_text="")

    # ------------------------------------------------------
    # Search dispatch
    # ------------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        mode = self._lookup_mode.currentText()

        if mode == "alias":
            self._load_by_alias(text)
        elif mode == "wikidata":
            self._load_by_location_field("wikidata", text)
        else:
            raise RuntimeError(f"Unknown lookup mode: {mode}")

    # ------------------------------------------------------
    # Alias-based lookup
    # ------------------------------------------------------

    def _load_by_alias(self, search_text: str) -> None:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        if not search_text:
            cur.execute(
                """
                SELECT location_id, alias
                FROM location_aliases
                ORDER BY alias
                LIMIT 200;
                """
            )
        else:
            norm = " ".join(search_text.lower().split())
            cur.execute(
                """
                SELECT location_id, alias
                FROM location_aliases
                WHERE normalized LIKE ?
                ORDER BY alias
                LIMIT 200;
                """,
                (f"{norm}%",),
            )

        rows = cur.fetchall()
        con.close()

        self._populate_alias_list(rows)

    # ------------------------------------------------------
    # Location-table lookup (osm_id / wikidata)
    # ------------------------------------------------------

    def _load_by_location_field(self, field: str, value: str) -> None:
        if not value:
            self._alias_list.clear()
            return

        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        try:
            cur.execute(
                f"""
                SELECT la.location_id, la.alias
                FROM locations l
                JOIN location_aliases la
                  ON la.location_id = l.location_id
                WHERE l.{field} = ?
                ORDER BY la.alias
                LIMIT 200;
                """,
                (value,),
            )
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                f"locations.{field} does not exist in schema"
            ) from e

        rows = cur.fetchall()
        con.close()

        self._populate_alias_list(rows)

    # ------------------------------------------------------
    # UI population
    # ------------------------------------------------------

    def _populate_alias_list(self, rows: list[sqlite3.Row]) -> None:
        print(f"[DEBUG] displaying {len(rows)} aliases")

        self._alias_list.clear()
        for row in rows:
            item = QListWidgetItem(row["alias"])
            item.setData(Qt.UserRole, row["location_id"])
            self._alias_list.addItem(item)

    # ------------------------------------------------------
    # Interaction
    # ------------------------------------------------------

    def _on_alias_clicked(self, item: QListWidgetItem) -> None:
        location_id = item.data(Qt.UserRole)

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
