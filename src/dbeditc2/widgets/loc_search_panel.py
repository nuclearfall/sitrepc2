# widgets/loc_search_panel.py
from __future__ import annotations

import sqlite3
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QComboBox,
    QPushButton,
)

from sitrepc2.config.paths import gazetteer_path


class LocationSearchPanel(QWidget):
    """
    Left-hand search panel for gazetteer locations.
    """

    # MUST be object to safely carry 64-bit location_id
    locationSelected = Signal(object)      # location_id
    createRequested = Signal()
    statusMessage = Signal(str)

    MODE_LOCATIONS = "Locations (name / alias)"
    MODE_ALIASES = "Aliases"
    MODE_OSM = "OSM ID"
    MODE_WIKIDATA = "Wikidata"

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._db_path = gazetteer_path()

        self.lookup_mode = QComboBox()
        self.lookup_mode.addItems([
            self.MODE_LOCATIONS,
            self.MODE_ALIASES,
            self.MODE_OSM,
            self.MODE_WIKIDATA,
        ])

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search…")

        self.results = QListWidget()

        self.add_new_btn = QPushButton("Add New Location")
        self.add_new_btn.clicked.connect(self.createRequested.emit)

        layout = QVBoxLayout(self)
        layout.addWidget(self.lookup_mode)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.results)
        layout.addWidget(self.add_new_btn)
        self.setLayout(layout)

        self.search_edit.textChanged.connect(self._run_search)
        self.lookup_mode.currentIndexChanged.connect(
            lambda: self._run_search(self.search_edit.text())
        )
        self.results.itemClicked.connect(self._on_item_clicked)

        self._run_search("")

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    def _run_search(self, text: str) -> None:
        self.results.clear()
        mode = self.lookup_mode.currentText()

        if mode == self.MODE_LOCATIONS:
            self._search_locations(text)
        elif mode == self.MODE_ALIASES:
            self._search_aliases(text)
        # elif mode == self.MODE_OSM:
        #     self._lookup_identifier("osm_id", text)
        elif mode == self.MODE_WIKIDATA:
            self._lookup_identifier("wikidata", text)

    def _search_locations(self, text: str) -> None:
        with self._conn() as con:
            rows = con.execute(
                """
                SELECT DISTINCT
                    l.location_id,
                    l.name,
                    l.place,
                    r.name AS region_name
                FROM locations l
                LEFT JOIN location_aliases a ON a.location_id = l.location_id
                LEFT JOIN location_regions lr ON lr.location_id = l.location_id
                LEFT JOIN regions r ON r.region_id = lr.region_id
                WHERE l.name LIKE ? OR a.alias LIKE ?
                ORDER BY l.name, r.name, l.place
                """,
                (f"%{text}%", f"%{text}%"),
            )

            for row in rows:
                label = (
                    f"{row['name']} "
                    f"({row['region_name'] or '—'}/{row['place'] or '—'})"
                )
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, row["location_id"])
                self.results.addItem(item)

    def _search_aliases(self, text: str) -> None:
        with self._conn() as con:
            rows = con.execute(
                """
                SELECT
                    a.alias,
                    l.location_id,
                    l.name,
                    l.place,
                    r.name AS region_name
                FROM location_aliases a
                JOIN locations l ON l.location_id = a.location_id
                LEFT JOIN location_regions lr ON lr.location_id = l.location_id
                LEFT JOIN regions r ON r.region_id = lr.region_id
                WHERE a.alias LIKE ?
                ORDER BY a.alias
                """,
                (f"%{text}%",),
            )

            for row in rows:
                label = (
                    f"{row['alias']} → {row['name']} "
                    f"({row['region_name'] or '—'}/{row['place'] or '—'})"
                )
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, row["location_id"])
                self.results.addItem(item)

    def _lookup_identifier(self, field: str, value: str) -> None:
        value = value.strip()
        if not value:
            return

        with self._conn() as con:
            row = con.execute(
                f"SELECT location_id FROM locations WHERE {field} = ?",
                (value,),
            ).fetchone()

            if row:
                # DO NOT cast — keep full 64-bit value
                self.locationSelected.emit(row["location_id"])
            else:
                self.statusMessage.emit(
                    f"No location found for {field}={value}"
                )

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        location_id = item.data(Qt.UserRole)
        if location_id is not None:
            # DO NOT cast — keep full 64-bit value
            self.locationSelected.emit(location_id)
