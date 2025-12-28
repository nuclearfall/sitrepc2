from __future__ import annotations

import sqlite3
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QFormLayout,
    QMessageBox,
    QComboBox,
)

from sitrepc2.config.paths import gazetteer_path


# ---------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------

def encode_coord_u64(lat: float, lon: float) -> int:
    lat = round(lat, 6)
    lon = round(lon, 6)
    lat_u32 = int((lat + 90.0) * 1_000_000)
    lon_u32 = int((lon + 180.0) * 1_000_000)
    return (lat_u32 << 32) | lon_u32


# ---------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------

class GazetteerWorkspace(QWidget):
    statusMessage = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._db_path = gazetteer_path()
        self._current_location_id: Optional[int] = None
        self._create_mode = False

        # --------------------------------------------------
        # Search pane
        # --------------------------------------------------

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search locations…")

        self.lookup_mode = QComboBox()
        self.lookup_mode.addItems(
            ["Locations (name / alias)", "Aliases", "OSM ID", "Wikidata"]
        )

        self.search_results = QListWidget()

        self.add_new_btn = QPushButton("Add New")
        self.add_new_btn.clicked.connect(self._enter_create_mode)

        self.search_edit.textChanged.connect(self._search)
        self.lookup_mode.currentIndexChanged.connect(
            lambda: self._search(self.search_edit.text())
        )
        self.search_results.itemClicked.connect(self._on_result_clicked)

        search_layout = QVBoxLayout()
        search_layout.addWidget(self.lookup_mode)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(self.search_results)
        search_layout.addWidget(self.add_new_btn)

        # --------------------------------------------------
        # Details pane
        # --------------------------------------------------

        self.id_label = QLabel("—")
        self.lat_edit = QLineEdit()
        self.lon_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.place_edit = QLineEdit()
        self.osm_edit = QLineEdit()
        self.wikidata_edit = QLineEdit()

        # Aliases
        self.alias_list = QListWidget()
        self.alias_edit = QLineEdit()
        self.add_alias_btn = QPushButton("Add Alias")
        self.remove_alias_btn = QPushButton("Remove Selected")

        self.add_alias_btn.clicked.connect(self._add_alias)
        self.remove_alias_btn.clicked.connect(self._remove_alias)

        # Group / Region
        self.group_combo = QComboBox()
        self.region_combo = QComboBox()

        # Actions
        self.save_btn = QPushButton("Save Changes")
        self.finalize_btn = QPushButton("Finalize Entry")

        self.save_btn.clicked.connect(self._save_existing)
        self.finalize_btn.clicked.connect(self._finalize_create)
        self.finalize_btn.hide()

        form = QFormLayout()
        form.addRow("Location ID", self.id_label)
        form.addRow("Latitude", self.lat_edit)
        form.addRow("Longitude", self.lon_edit)
        form.addRow("Name", self.name_edit)
        form.addRow("Place", self.place_edit)
        form.addRow("OSM ID", self.osm_edit)
        form.addRow("Wikidata", self.wikidata_edit)
        form.addRow(QLabel("Aliases"), self.alias_list)
        form.addRow(self.alias_edit, self.add_alias_btn)
        form.addRow(self.remove_alias_btn)
        form.addRow("Group", self.group_combo)
        form.addRow("Region", self.region_combo)
        form.addRow(self.save_btn)
        form.addRow(self.finalize_btn)

        # --------------------------------------------------
        # Main layout
        # --------------------------------------------------

        main = QHBoxLayout(self)
        main.addLayout(search_layout, 1)
        main.addLayout(form, 2)
        self.setLayout(main)

        self._load_groups()
        self._load_regions()
        self._search("")

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _search(self, text: str) -> None:
        self.search_results.clear()
        mode = self.lookup_mode.currentText()

        with self._conn() as con:
            if mode.startswith("Locations"):
                rows = con.execute(
                    """
                    SELECT DISTINCT l.location_id, l.name
                    FROM locations l
                    LEFT JOIN location_aliases a USING (location_id)
                    WHERE l.name LIKE ? OR a.alias LIKE ?
                    ORDER BY l.name
                    """,
                    (f"%{text}%", f"%{text}%"),
                )
                for r in rows:
                    item = QListWidgetItem(r["name"] or f"(id {r['location_id']})")
                    item.setData(Qt.UserRole, ("location", r["location_id"]))
                    self.search_results.addItem(item)

            elif mode == "Aliases":
                rows = con.execute(
                    """
                    SELECT a.alias, a.location_id, l.name
                    FROM location_aliases a
                    JOIN locations l USING (location_id)
                    WHERE a.alias LIKE ?
                    ORDER BY a.alias
                    """,
                    (f"%{text}%",),
                )
                for r in rows:
                    label = f"{r['alias']} → {r['name']}"
                    item = QListWidgetItem(label)
                    item.setData(Qt.UserRole, ("location", r["location_id"]))
                    self.search_results.addItem(item)

            elif mode == "OSM ID":
                row = con.execute(
                    "SELECT location_id FROM locations WHERE osm_id = ?",
                    (text,),
                ).fetchone()
                if row:
                    self._load_location(row["location_id"])

            elif mode == "Wikidata":
                row = con.execute(
                    "SELECT location_id FROM locations WHERE wikidata = ?",
                    (text,),
                ).fetchone()
                if row:
                    self._load_location(row["location_id"])

    def _on_result_clicked(self, item: QListWidgetItem) -> None:
        kind, location_id = item.data(Qt.UserRole)
        if kind == "location":
            self._load_location(location_id)

    # ------------------------------------------------------------------
    # Load location
    # ------------------------------------------------------------------

    def _load_location(self, location_id: int) -> None:
        self._create_mode = False
        self.finalize_btn.hide()
        self.save_btn.show()

        with self._conn() as con:
            loc = con.execute(
                "SELECT * FROM locations WHERE location_id = ?",
                (location_id,),
            ).fetchone()

            self._current_location_id = location_id
            self.id_label.setText(str(location_id))
            self.lat_edit.setText(str(loc["lat"]))
            self.lon_edit.setText(str(loc["lon"]))
            self.name_edit.setText(loc["name"] or "")
            self.place_edit.setText(loc["place"] or "")
            self.osm_edit.setText(loc["osm_id"] or "")
            self.wikidata_edit.setText(loc["wikidata"] or "")

            self.alias_list.clear()
            for a in con.execute(
                "SELECT alias FROM location_aliases WHERE location_id = ? ORDER BY alias",
                (location_id,),
            ):
                self.alias_list.addItem(a["alias"])

    # ------------------------------------------------------------------
    # Alias editing
    # ------------------------------------------------------------------

    def _add_alias(self) -> None:
        alias = self.alias_edit.text().strip()
        if not alias:
            return
        self.alias_list.addItem(alias)
        self.alias_edit.clear()

    def _remove_alias(self) -> None:
        for item in self.alias_list.selectedItems():
            self.alias_list.takeItem(self.alias_list.row(item))

    # ------------------------------------------------------------------
    # Create mode
    # ------------------------------------------------------------------

    def _enter_create_mode(self) -> None:
        self._create_mode = True
        self._current_location_id = None

        for w in (
            self.lat_edit,
            self.lon_edit,
            self.name_edit,
            self.place_edit,
            self.osm_edit,
            self.wikidata_edit,
        ):
            w.clear()

        self.alias_list.clear()
        self.id_label.setText("—")

        self.save_btn.hide()
        self.finalize_btn.show()

    def _finalize_create(self) -> None:
        try:
            lat = float(self.lat_edit.text())
            lon = float(self.lon_edit.text())
        except ValueError:
            QMessageBox.critical(self, "Error", "Invalid latitude/longitude.")
            return

        location_id = encode_coord_u64(lat, lon)

        try:
            with self._conn() as con:
                con.execute(
                    """
                    INSERT INTO locations (
                        location_id, lat, lon, name, place, osm_id, wikidata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        location_id,
                        lat,
                        lon,
                        self.name_edit.text() or None,
                        self.place_edit.text() or None,
                        self.osm_edit.text() or None,
                        self.wikidata_edit.text() or None,
                    ),
                )

                for i in range(self.alias_list.count()):
                    alias = self.alias_list.item(i).text()
                    con.execute(
                        """
                        INSERT INTO location_aliases
                        (location_id, alias, normalized)
                        VALUES (?, ?, ?)
                        """,
                        (location_id, alias, alias.lower()),
                    )

            QMessageBox.information(
                self, "Created", f"Location {location_id} created."
            )
            self.statusMessage.emit(f"Created location {location_id}")
            self._load_location(location_id)

        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Database error", str(e))

    # ------------------------------------------------------------------
    # Save existing
    # ------------------------------------------------------------------

    def _save_existing(self) -> None:
        if not self._current_location_id:
            return

        with self._conn() as con:
            con.execute(
                """
                UPDATE locations
                SET name = ?, place = ?, osm_id = ?, wikidata = ?
                WHERE location_id = ?
                """,
                (
                    self.name_edit.text() or None,
                    self.place_edit.text() or None,
                    self.osm_edit.text() or None,
                    self.wikidata_edit.text() or None,
                    self._current_location_id,
                ),
            )

            con.execute(
                "DELETE FROM location_aliases WHERE location_id = ?",
                (self._current_location_id,),
            )

            for i in range(self.alias_list.count()):
                alias = self.alias_list.item(i).text()
                con.execute(
                    """
                    INSERT INTO location_aliases
                    (location_id, alias, normalized)
                    VALUES (?, ?, ?)
                    """,
                    (self._current_location_id, alias, alias.lower()),
                )

        QMessageBox.information(self, "Saved", "Changes saved.")
