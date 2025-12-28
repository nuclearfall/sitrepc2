# widgets/loc_form.py
from __future__ import annotations

import sqlite3
from typing import Optional, List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QFormLayout,
    QMessageBox,
    QComboBox,
)

from sitrepc2.config.paths import gazetteer_path


# ---------------------------------------------------------------------
# Identity helper
# ---------------------------------------------------------------------

def encode_coord_u64(lat: float, lon: float) -> int:
    lat = round(lat, 6)
    lon = round(lon, 6)
    lat_u32 = int((lat + 90.0) * 1_000_000)
    lon_u32 = int((lon + 180.0) * 1_000_000)
    return (lat_u32 << 32) | lon_u32


# ---------------------------------------------------------------------
# Location Form
# ---------------------------------------------------------------------

class LocationForm(QWidget):
    """
    Right-hand form for viewing, editing, and creating locations.
    """

    statusMessage = Signal(str)
    locationCreated = Signal(int)   # new location_id
    locationUpdated = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._db_path = gazetteer_path()
        self._location_id: Optional[int] = None
        self._create_mode = False

        # --------------------------------------------------
        # Widgets
        # --------------------------------------------------

        self.id_label = QLabel("—")
        self.lat_edit = QLineEdit()
        self.lon_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.place_edit = QLineEdit()
        self.osm_edit = QLineEdit()
        self.wikidata_edit = QLineEdit()

        self.alias_list = QListWidget()
        self.alias_edit = QLineEdit()
        self.add_alias_btn = QPushButton("Add Alias")
        self.remove_alias_btn = QPushButton("Remove Selected")

        self.group_combo = QComboBox()
        self.region_combo = QComboBox()

        self.save_btn = QPushButton("Save Changes")
        self.finalize_btn = QPushButton("Finalize Entry")
        self.finalize_btn.hide()

        # --------------------------------------------------
        # Layout
        # --------------------------------------------------

        form = QFormLayout(self)
        form.addRow("Location ID", self.id_label)
        form.addRow("Latitude", self.lat_edit)
        form.addRow("Longitude", self.lon_edit)
        form.addRow("Name", self.name_edit)
        form.addRow("Place", self.place_edit)
        form.addRow("OSM ID", self.osm_edit)
        form.addRow("Wikidata", self.wikidata_edit)

        form.addRow("Aliases", self.alias_list)
        form.addRow(self.alias_edit, self.add_alias_btn)
        form.addRow(self.remove_alias_btn)

        form.addRow("Group", self.group_combo)
        form.addRow("Region", self.region_combo)

        form.addRow(self.save_btn)
        form.addRow(self.finalize_btn)

        # --------------------------------------------------
        # Signals
        # --------------------------------------------------

        self.add_alias_btn.clicked.connect(self._add_alias)
        self.remove_alias_btn.clicked.connect(self._remove_alias)
        self.save_btn.clicked.connect(self._save_existing)
        self.finalize_btn.clicked.connect(self._finalize_create)

        self._load_groups()
        self._load_regions()
        self._set_view_mode()

    # --------------------------------------------------
    # DB helpers
    # --------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    def _load_groups(self) -> None:
        self.group_combo.clear()
        self.group_combo.addItem("(None)", None)
        with self._conn() as con:
            for r in con.execute("SELECT group_id, name FROM groups ORDER BY name"):
                self.group_combo.addItem(r["name"], r["group_id"])

    def _load_regions(self) -> None:
        self.region_combo.clear()
        self.region_combo.addItem("(None)", None)
        with self._conn() as con:
            for r in con.execute("SELECT region_id, name FROM regions ORDER BY name"):
                self.region_combo.addItem(r["name"], r["region_id"])

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def load_location(self, location_id: int) -> None:
        """Load an existing location."""
        self._location_id = location_id
        self._create_mode = False
        self.finalize_btn.hide()
        self.save_btn.show()

        with self._conn() as con:
            loc = con.execute(
                "SELECT * FROM locations WHERE location_id = ?",
                (location_id,),
            ).fetchone()

            if not loc:
                QMessageBox.critical(self, "Error", "Location not found")
                return

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

    def enter_create_mode(self) -> None:
        """Prepare form for creating a new location."""
        self._location_id = None
        self._create_mode = True

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

    # --------------------------------------------------
    # Alias editing
    # --------------------------------------------------

    def _add_alias(self) -> None:
        alias = self.alias_edit.text().strip()
        if alias:
            self.alias_list.addItem(alias)
            self.alias_edit.clear()

    def _remove_alias(self) -> None:
        for item in self.alias_list.selectedItems():
            self.alias_list.takeItem(self.alias_list.row(item))

    # --------------------------------------------------
    # Save / create
    # --------------------------------------------------

    def _save_existing(self) -> None:
        if not self._location_id:
            return

        with self._conn() as con:
            con.execute(
                """
                UPDATE locations
                SET name=?, place=?, osm_id=?, wikidata=?
                WHERE location_id=?
                """,
                (
                    self.name_edit.text() or None,
                    self.place_edit.text() or None,
                    self.osm_edit.text() or None,
                    self.wikidata_edit.text() or None,
                    self._location_id,
                ),
            )

            con.execute(
                "DELETE FROM location_aliases WHERE location_id=?",
                (self._location_id,),
            )
            for i in range(self.alias_list.count()):
                alias = self.alias_list.item(i).text()
                con.execute(
                    """
                    INSERT INTO location_aliases
                    (location_id, alias, normalized)
                    VALUES (?, ?, ?)
                    """,
                    (self._location_id, alias, alias.lower()),
                )

        self.statusMessage.emit("Location updated")
        self.locationUpdated.emit(self._location_id)

    def _finalize_create(self) -> None:
        try:
            lat = float(self.lat_edit.text())
            lon = float(self.lon_edit.text())
        except ValueError:
            QMessageBox.critical(self, "Error", "Invalid latitude/longitude")
            return

        location_id = encode_coord_u64(lat, lon)

        try:
            with self._conn() as con:
                con.execute(
                    """
                    INSERT INTO locations
                    (location_id, lat, lon, name, place, osm_id, wikidata)
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

            QMessageBox.information(self, "Created", f"Location {location_id} created")
            self.locationCreated.emit(location_id)

        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Database error", str(e))
