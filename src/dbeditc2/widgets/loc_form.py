# widgets/loc_form.py
from __future__ import annotations

import os
import sqlite3
import sys
import threading
from typing import Optional

from PySide6.QtCore import Signal, Slot
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
# Debug helper
# ---------------------------------------------------------------------

def _dbg(msg: str) -> None:
    print(f"[loc_form][tid={threading.get_ident()}] {msg}", file=sys.stderr, flush=True)


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
    locationCreated = Signal(object)   # 64-bit safe
    locationUpdated = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._db_path = gazetteer_path()
        self._location_id: Optional[int] = None
        self._create_mode = False

        _dbg(f"INIT gazetteer_path() -> {self._db_path!r}")
        try:
            exists = os.path.exists(self._db_path)
            size = os.path.getsize(self._db_path) if exists else -1
            _dbg(f"DB exists={exists} size={size}")
        except Exception as e:
            _dbg(f"DB stat error: {e!r}")

        # --------------------------------------------------
        # Widgets
        # --------------------------------------------------

        self.id_label = QLabel("—")
        self.lat_edit = QLineEdit()
        self.lon_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.place_edit = QLineEdit()
        # self.osm_edit = QLineEdit()
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
        # form.addRow("OSM ID", self.osm_edit)
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
        _dbg(f"OPEN DB: {self._db_path!r}")
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        fk = con.execute("PRAGMA foreign_keys;").fetchone()[0]
        _dbg(f"PRAGMA foreign_keys={fk}")
        return con

    def _load_groups(self) -> None:
        _dbg("LOAD groups -> combo")
        self.group_combo.clear()
        self.group_combo.addItem("(None)", None)
        with self._conn() as con:
            rows = list(con.execute("SELECT group_id, name FROM groups ORDER BY name"))
            _dbg(f"groups rows={len(rows)}")
            for r in rows:
                self.group_combo.addItem(r["name"], r["group_id"])

    def _load_regions(self) -> None:
        _dbg("LOAD regions -> combo")
        self.region_combo.clear()
        self.region_combo.addItem("(None)", None)
        with self._conn() as con:
            rows = list(con.execute("SELECT region_id, name FROM regions ORDER BY name"))
            _dbg(f"regions rows={len(rows)}")
            for r in rows:
                self.region_combo.addItem(r["name"], r["region_id"])

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    @Slot(object)
    def load_location(self, location_id: object) -> None:
        _dbg(f"LOAD location_id={location_id!r} type={type(location_id)}")
        self._location_id = location_id
        self._create_mode = False
        self.finalize_btn.hide()
        self.save_btn.show()

        with self._conn() as con:
            loc = con.execute(
                "SELECT * FROM locations WHERE location_id = ?",
                (location_id,),
            ).fetchone()

            _dbg(f"SELECT locations by id -> found={bool(loc)}")

            if not loc:
                QMessageBox.critical(self, "Error", "Location not found")
                return

            self.id_label.setText(str(location_id))
            self.lat_edit.setText(str(loc["lat"]))
            self.lon_edit.setText(str(loc["lon"]))
            self.name_edit.setText(loc["name"] or "")
            self.place_edit.setText(loc["place"] or "")
            self.wikidata_edit.setText(
                loc["wikidata"] if "wikidata" in loc.keys() and loc["wikidata"] else ""
            )

            # aliases
            self.alias_list.clear()
            alias_rows = list(
                con.execute(
                    "SELECT alias FROM location_aliases WHERE location_id=? ORDER BY alias",
                    (location_id,),
                )
            )
            _dbg(f"aliases rows={len(alias_rows)}")
            for a in alias_rows:
                self.alias_list.addItem(a["alias"])

            # group
            gid = con.execute(
                "SELECT group_id FROM location_groups WHERE location_id=?",
                (location_id,),
            ).fetchone()
            _dbg(f"group row={dict(gid) if gid else None}")
            self.group_combo.setCurrentIndex(
                self.group_combo.findData(gid["group_id"]) if gid else 0
            )

            # region
            rid = con.execute(
                "SELECT region_id FROM location_regions WHERE location_id=?",
                (location_id,),
            ).fetchone()
            _dbg(f"region row={dict(rid) if rid else None}")
            self.region_combo.setCurrentIndex(
                self.region_combo.findData(rid["region_id"]) if rid else 0
            )

    def enter_create_mode(self) -> None:
        _dbg("ENTER create mode")
        self._location_id = None
        self._create_mode = True

        for w in (
            self.lat_edit,
            self.lon_edit,
            self.name_edit,
            self.place_edit,
            self.wikidata_edit,
        ):
            w.clear()

        self.alias_list.clear()
        self.group_combo.setCurrentIndex(0)
        self.region_combo.setCurrentIndex(0)
        self.id_label.setText("—")

        self.save_btn.hide()
        self.finalize_btn.show()

    # --------------------------------------------------
    # Alias editing
    # --------------------------------------------------

    def _add_alias(self) -> None:
        alias = self.alias_edit.text().strip()
        _dbg(f"ADD alias clicked -> {alias!r}")
        if alias:
            self.alias_list.addItem(alias)
            _dbg(f"alias_list count now {self.alias_list.count()}")
            self.alias_edit.clear()

    def _remove_alias(self) -> None:
        selected = self.alias_list.selectedItems()
        _dbg(f"REMOVE alias clicked -> selected={len(selected)}")
        for item in selected:
            txt = item.text()
            self.alias_list.takeItem(self.alias_list.row(item))
            _dbg(f"removed alias {txt!r}; count now {self.alias_list.count()}")

    # --------------------------------------------------
    # Save / create
    # --------------------------------------------------

    def _set_view_mode(self) -> None:
        _dbg("SET view mode")
        self._create_mode = False
        self.save_btn.show()
        self.finalize_btn.hide()

    def _save_existing(self) -> None:
        _dbg(f"SAVE existing clicked; _location_id={self._location_id!r}")
        if not self._location_id:
            _dbg("SAVE existing aborted: no _location_id")
            return

        with self._conn() as con:
            cur = con.execute(
                """
                UPDATE locations
                SET name=?, place=?, wikidata=?
                WHERE location_id=?
                """,
                (
                    self.name_edit.text() or None,
                    self.place_edit.text() or None,
                    self.wikidata_edit.text() or None,
                    self._location_id,
                ),
            )
            _dbg(f"UPDATE locations rowcount={cur.rowcount} total_changes={con.total_changes}")

            cur = con.execute(
                "DELETE FROM location_aliases WHERE location_id=?",
                (self._location_id,),
            )
            _dbg(f"DELETE location_aliases rowcount={cur.rowcount}")

            for i in range(self.alias_list.count()):
                a = self.alias_list.item(i).text()
                cur = con.execute(
                    """
                    INSERT INTO location_aliases
                    (location_id, alias, normalized)
                    VALUES (?, ?, ?)
                    """,
                    (self._location_id, a, a.lower()),
                )
                _dbg(f"INSERT alias {a!r} rowcount={cur.rowcount}")

            cur = con.execute("DELETE FROM location_groups WHERE location_id=?", (self._location_id,))
            _dbg(f"DELETE location_groups rowcount={cur.rowcount}")
            cur = con.execute("DELETE FROM location_regions WHERE location_id=?", (self._location_id,))
            _dbg(f"DELETE location_regions rowcount={cur.rowcount}")

            gid = self.group_combo.currentData()
            rid = self.region_combo.currentData()
            _dbg(f"current group={gid!r} region={rid!r}")

            if gid is not None:
                cur = con.execute(
                    "INSERT INTO location_groups VALUES (?, ?)",
                    (self._location_id, gid),
                )
                _dbg(f"INSERT location_groups rowcount={cur.rowcount}")

            if rid is not None:
                cur = con.execute(
                    "INSERT INTO location_regions VALUES (?, ?)",
                    (self._location_id, rid),
                )
                _dbg(f"INSERT location_regions rowcount={cur.rowcount}")

            # Verify row exists in this same connection
            exists = con.execute(
                "SELECT COUNT(*) FROM locations WHERE location_id=?",
                (self._location_id,),
            ).fetchone()[0]
            _dbg(f"VERIFY locations exists after save -> {exists}")

            _dbg(f"END SAVE total_changes={con.total_changes}")

        self.statusMessage.emit("Location updated")
        self.locationUpdated.emit(self._location_id)

    def _finalize_create(self) -> None:
        _dbg("FINALIZE create clicked")
        try:
            lat = float(self.lat_edit.text())
            lon = float(self.lon_edit.text())
        except ValueError:
            _dbg("FINALIZE create: invalid lat/lon")
            QMessageBox.critical(self, "Error", "Invalid latitude/longitude")
            return

        location_id = encode_coord_u64(lat, lon)
        _dbg(f"computed location_id={location_id} (0x{location_id:016x}) lat={lat} lon={lon}")

        try:
            with self._conn() as con:
                cur = con.execute(
                    """
                    INSERT INTO locations
                    (location_id, lat, lon, name, place, wikidata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        location_id,
                        lat,
                        lon,
                        self.name_edit.text() or None,
                        self.place_edit.text() or None,
                        self.wikidata_edit.text() or None,
                    ),
                )
                _dbg(f"INSERT locations rowcount={cur.rowcount} total_changes={con.total_changes}")

                for i in range(self.alias_list.count()):
                    a = self.alias_list.item(i).text()
                    cur = con.execute(
                        """
                        INSERT INTO location_aliases
                        (location_id, alias, normalized)
                        VALUES (?, ?, ?)
                        """,
                        (location_id, a, a.lower()),
                    )
                    _dbg(f"INSERT alias {a!r} rowcount={cur.rowcount}")

                gid = self.group_combo.currentData()
                rid = self.region_combo.currentData()
                _dbg(f"current group={gid!r} region={rid!r}")

                if gid is not None:
                    cur = con.execute(
                        "INSERT INTO location_groups VALUES (?, ?)",
                        (location_id, gid),
                    )
                    _dbg(f"INSERT location_groups rowcount={cur.rowcount}")

                if rid is not None:
                    cur = con.execute(
                        "INSERT INTO location_regions VALUES (?, ?)",
                        (location_id, rid),
                    )
                    _dbg(f"INSERT location_regions rowcount={cur.rowcount}")

                # Verify row exists in this same connection
                exists = con.execute(
                    "SELECT COUNT(*) FROM locations WHERE location_id=?",
                    (location_id,),
                ).fetchone()[0]
                _dbg(f"VERIFY locations exists after insert -> {exists}")

                # Also verify DB identity from SQLite itself
                try:
                    main_db = con.execute("PRAGMA database_list;").fetchall()
                    _dbg(f"PRAGMA database_list -> {[(r[1], r[2]) for r in main_db]}")
                except Exception as e:
                    _dbg(f"PRAGMA database_list failed: {e!r}")

                _dbg(f"END CREATE total_changes={con.total_changes}")

            QMessageBox.information(self, "Created", f"Location {location_id} created")
            self.locationCreated.emit(location_id)

        except sqlite3.IntegrityError as e:
            _dbg(f"IntegrityError: {e!r}")
            QMessageBox.critical(self, "Database error", str(e))
        except sqlite3.Error as e:
            _dbg(f"sqlite3.Error: {e!r}")
            QMessageBox.critical(self, "Database error", str(e))
        except Exception as e:
            _dbg(f"Unexpected error: {e!r}")
            QMessageBox.critical(self, "Error", str(e))
