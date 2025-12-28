from __future__ import annotations

import sqlite3
from typing import Optional, Tuple

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
    """Encode (lat, lon) into a single 64-bit integer key with 6-decimal precision."""
    lat = round(lat, 6)
    lon = round(lon, 6)

    lat_u32 = int((lat + 90.0) * 1_000_000)
    lon_u32 = int((lon + 180.0) * 1_000_000)

    return (lat_u32 << 32) | lon_u32


def _combo_set_by_user_data(combo: QComboBox, value) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return
    combo.setCurrentIndex(0)


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
        self.lookup_mode = QComboBox()
        self.lookup_mode.addItems(
            [
                "Locations (name / alias)",  # default
                "Aliases",
                "OSM ID",
                "Wikidata",
            ]
        )

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search…")

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

        # Aliases UI (correct pattern)
        self.alias_list = QListWidget()
        self.alias_edit = QLineEdit()
        self.alias_edit.setPlaceholderText("Enter alias…")
        self.add_alias_btn = QPushButton("Add Alias")
        self.remove_alias_btn = QPushButton("Remove Selected")

        self.add_alias_btn.clicked.connect(self._add_alias_to_list)
        self.remove_alias_btn.clicked.connect(self._remove_selected_aliases)

        # Group / Region single-select
        self.group_combo = QComboBox()
        self.region_combo = QComboBox()

        # Actions
        self.save_btn = QPushButton("Save Changes")
        self.finalize_btn = QPushButton("Finalize Entry")
        self.finalize_btn.hide()

        self.save_btn.clicked.connect(self._save_existing)
        self.finalize_btn.clicked.connect(self._finalize_create)

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

        # populate dropdowns + initial search
        self._load_groups()
        self._load_regions()
        self._search("")

        # default: not creating
        self._set_mode_view()

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    # ------------------------------------------------------------------
    # Group / Region loaders (these were missing previously)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Search behavior
    # ------------------------------------------------------------------

    def _search(self, text: str) -> None:
        """Populate left results list according to lookup mode."""
        mode = self.lookup_mode.currentText()
        self.search_results.clear()

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
                    label = r["name"] or f"(id {r['location_id']})"
                    item = QListWidgetItem(label)
                    item.setData(Qt.UserRole, ("location", int(r["location_id"])))
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
                    label = f"{r['alias']} → {r['name'] or r['location_id']}"
                    item = QListWidgetItem(label)
                    item.setData(Qt.UserRole, ("location", int(r["location_id"])))
                    self.search_results.addItem(item)

            elif mode == "OSM ID":
                if not text.strip():
                    return
                row = con.execute(
                    "SELECT location_id FROM locations WHERE osm_id = ?",
                    (text.strip(),),
                ).fetchone()
                if row:
                    self._load_location(int(row["location_id"]))
                else:
                    self.statusMessage.emit("No location found for osm_id")

            elif mode == "Wikidata":
                if not text.strip():
                    return
                row = con.execute(
                    "SELECT location_id FROM locations WHERE wikidata = ?",
                    (text.strip(),),
                ).fetchone()
                if row:
                    self._load_location(int(row["location_id"]))
                else:
                    self.statusMessage.emit("No location found for wikidata")

    def _on_result_clicked(self, item: QListWidgetItem) -> None:
        kind, location_id = item.data(Qt.UserRole)
        if kind == "location":
            self._load_location(int(location_id))

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _set_mode_view(self) -> None:
        self._create_mode = False
        self.finalize_btn.hide()
        self.save_btn.show()
        # In view mode, lat/lon normally shouldn’t be casually edited because id is derived.
        # But you can still edit if you want; leaving enabled for now.
        self.statusMessage.emit("View mode")

    def _set_mode_create(self) -> None:
        self._create_mode = True
        self.save_btn.hide()
        self.finalize_btn.show()
        self.statusMessage.emit("Create mode")

    # ------------------------------------------------------------------
    # Load location details (must repaint everything every time)
    # ------------------------------------------------------------------

    def _load_location(self, location_id: int) -> None:
        self._set_mode_view()
        self._current_location_id = location_id

        with self._conn() as con:
            loc = con.execute(
                "SELECT * FROM locations WHERE location_id = ?",
                (location_id,),
            ).fetchone()

            if not loc:
                QMessageBox.critical(self, "Error", f"Location not found: {location_id}")
                return

            self.id_label.setText(str(location_id))
            self.lat_edit.setText(str(loc["lat"]))
            self.lon_edit.setText(str(loc["lon"]))
            self.name_edit.setText(loc["name"] or "")
            self.place_edit.setText(loc["place"] or "")
            self.osm_edit.setText(loc["osm_id"] or "")
            self.wikidata_edit.setText(loc["wikidata"] or "")

            # Aliases
            self.alias_list.clear()
            for a in con.execute(
                "SELECT alias FROM location_aliases WHERE location_id = ? ORDER BY alias",
                (location_id,),
            ):
                self.alias_list.addItem(a["alias"])

            # Group (expect 0..1)
            group_rows = con.execute(
                "SELECT group_id FROM location_groups WHERE location_id = ?",
                (location_id,),
            ).fetchall()
            group_id = group_rows[0]["group_id"] if group_rows else None
            _combo_set_by_user_data(self.group_combo, group_id)

            # Region (expect 0..1)
            region_rows = con.execute(
                "SELECT region_id FROM location_regions WHERE location_id = ?",
                (location_id,),
            ).fetchall()
            region_id = region_rows[0]["region_id"] if region_rows else None
            _combo_set_by_user_data(self.region_combo, region_id)

            if len(group_rows) > 1:
                self.statusMessage.emit(
                    f"Warning: location_id={location_id} has multiple groups; showing first."
                )
            if len(region_rows) > 1:
                self.statusMessage.emit(
                    f"Warning: location_id={location_id} has multiple regions; showing first."
                )

    # ------------------------------------------------------------------
    # Alias list editing (in-memory until save/finalize)
    # ------------------------------------------------------------------

    def _add_alias_to_list(self) -> None:
        alias = self.alias_edit.text().strip()
        if not alias:
            return

        # prevent duplicates in UI
        existing = {self.alias_list.item(i).text() for i in range(self.alias_list.count())}
        if alias in existing:
            self.statusMessage.emit("Alias already present")
            self.alias_edit.clear()
            return

        self.alias_list.addItem(alias)
        self.alias_edit.clear()

    def _remove_selected_aliases(self) -> None:
        for item in self.alias_list.selectedItems():
            self.alias_list.takeItem(self.alias_list.row(item))

    # ------------------------------------------------------------------
    # Create mode
    # ------------------------------------------------------------------

    def _enter_create_mode(self) -> None:
        self._current_location_id = None
        self.id_label.setText("—")

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
        self.alias_edit.clear()
        self.group_combo.setCurrentIndex(0)
        self.region_combo.setCurrentIndex(0)

        self._set_mode_create()

    def _finalize_create(self) -> None:
        # Validate lat/lon
        try:
            lat = float(self.lat_edit.text().strip())
            lon = float(self.lon_edit.text().strip())
        except ValueError:
            QMessageBox.critical(self, "Error", "Invalid latitude/longitude.")
            return

        location_id = encode_coord_u64(lat, lon)

        # Collect aliases
        aliases = [
            self.alias_list.item(i).text()
            for i in range(self.alias_list.count())
        ]

        group_id = self.group_combo.currentData()
        region_id = self.region_combo.currentData()

        osm_id = self.osm_edit.text().strip() or None
        wikidata = self.wikidata_edit.text().strip() or None

        try:
            with self._conn() as con:
                # --------------------------------------------------
                # Insert location
                # --------------------------------------------------
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
                        self.name_edit.text().strip() or None,
                        self.place_edit.text().strip() or None,
                        osm_id,
                        wikidata,
                    ),
                )

                # --------------------------------------------------
                # Insert aliases
                # --------------------------------------------------
                for alias in aliases:
                    con.execute(
                        """
                        INSERT INTO location_aliases
                            (location_id, alias, normalized)
                        VALUES (?, ?, ?)
                        """,
                        (location_id, alias, alias.lower()),
                    )

                # --------------------------------------------------
                # Insert single group / region pivots (optional)
                # --------------------------------------------------
                if group_id is not None:
                    con.execute(
                        """
                        INSERT INTO location_groups
                            (location_id, group_id)
                        VALUES (?, ?)
                        """,
                        (location_id, group_id),
                    )

                if region_id is not None:
                    con.execute(
                        """
                        INSERT INTO location_regions
                            (location_id, region_id)
                        VALUES (?, ?)
                        """,
                        (location_id, region_id),
                    )

            QMessageBox.information(
                self,
                "Created",
                f"Location {location_id} created.",
            )
            self.statusMessage.emit(f"Created location {location_id}")

            # Reload newly created record
            self._load_location(location_id)

        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Database error", str(e))


    # ------------------------------------------------------------------
    # Save existing
    # ------------------------------------------------------------------

    def _save_existing(self) -> None:
        if not self._location_id:
            return

        group_id = self.group_combo.currentData()
        region_id = self.region_combo.currentData()

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

            con.execute("DELETE FROM location_aliases WHERE location_id=?", (self._location_id,))
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

            # NEW: enforce single group / region
            con.execute("DELETE FROM location_groups WHERE location_id=?", (self._location_id,))
            if group_id is not None:
                con.execute(
                    "INSERT INTO location_groups (location_id, group_id) VALUES (?, ?)",
                    (self._location_id, group_id),
                )

            con.execute("DELETE FROM location_regions WHERE location_id=?", (self._location_id,))
            if region_id is not None:
                con.execute(
                    "INSERT INTO location_regions (location_id, region_id) VALUES (?, ?)",
                    (self._location_id, region_id),
                )

        self.statusMessage.emit("Location updated")
        self.locationUpdated.emit(self._location_id)


        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Database error", str(e))
