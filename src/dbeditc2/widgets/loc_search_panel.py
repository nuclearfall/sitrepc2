# widgets/loc_search_panel.py
from __future__ import annotations

import os
import sqlite3
import sys
import threading
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


def _dbg(msg: str) -> None:
    print(f"[loc_search_panel][tid={threading.get_ident()}] {msg}", file=sys.stderr, flush=True)


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
        _dbg(f"INIT gazetteer_path() -> {self._db_path!r}")
        try:
            exists = os.path.exists(self._db_path)
            size = os.path.getsize(self._db_path) if exists else -1
            _dbg(f"DB exists={exists} size={size}")
        except Exception as e:
            _dbg(f"DB stat error: {e!r}")

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
        self.add_new_btn.clicked.connect(self._on_add_new_clicked)

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
        self.results.setSelectionMode(QListWidget.ExtendedSelection)

        self._run_search("")

    def _on_add_new_clicked(self) -> None:
        _dbg("Add New Location clicked -> createRequested.emit()")
        self.createRequested.emit()

    def _conn(self) -> sqlite3.Connection:
        _dbg(f"OPEN DB: {self._db_path!r}")
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        fk = con.execute("PRAGMA foreign_keys;").fetchone()[0]
        _dbg(f"PRAGMA foreign_keys={fk}")
        return con

    def _run_search(self, text: str) -> None:
        mode = self.lookup_mode.currentText()
        _dbg(f"RUN search mode={mode!r} text={text!r}")
        self.results.clear()

        if mode == self.MODE_LOCATIONS:
            self._search_locations(text)
        elif mode == self.MODE_ALIASES:
            self._search_aliases(text)
        elif mode == self.MODE_WIKIDATA:
            self._lookup_identifier("wikidata", text)

    def _search_locations(self, text: str) -> None:
        with self._conn() as con:
            rows = list(con.execute(
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
            ))
            _dbg(f"search_locations rows={len(rows)}")
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
            rows = list(con.execute(
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
            ))
            _dbg(f"search_aliases rows={len(rows)}")
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
        _dbg(f"lookup_identifier field={field!r} value={value!r}")
        if not value:
            _dbg("lookup_identifier early return: empty value")
            return

        with self._conn() as con:
            row = con.execute(
                f"SELECT location_id FROM locations WHERE {field} = ?",
                (value,),
            ).fetchone()

            _dbg(f"lookup_identifier found={bool(row)}")
            if row:
                lid = row["location_id"]
                _dbg(f"emit locationSelected lid={lid!r} type={type(lid)}")
                self.locationSelected.emit(lid)
            else:
                self.statusMessage.emit(
                    f"No location found for {field}={value}"
                )

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        items = self.results.selectedItems()
        lids = [it.data(Qt.UserRole) for it in items if it.data(Qt.UserRole) is not None]

        if lids:
            # single → old behavior preserved
            if len(lids) == 1:
                self.locationSelected.emit(lids[0])
            else:
                self.locationSelected.emit(lids)
