# widgets/loc_form.py
from __future__ import annotations

import os
import sqlite3
import sys
import threading
from typing import Optional, Sequence

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
    locationCreated = Signal(object)   # opaque 64-bit ID
    locationUpdated = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._db_path = gazetteer_path()

        # Selection state
        self._location_id: Optional[object] = None
        self._location_ids: list[object] = []

        self._create_mode = False

        # --------------------------------------------------
        # Widgets
        # --------------------------------------------------

        self.id_label = QLabel("—")
        self.lat_edit = QLineEdit()
        self.lon_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.place_edit = QLineEdit()
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
    # Load logic
    # --------------------------------------------------

    @Slot(object)
    def load_location(self, location_id_or_ids: object) -> None:
        if isinstance(location_id_or_ids, (list, tuple)):
            self._load_multiple(list(location_id_or_ids))
        else:
            self._load_single(location_id_or_ids)

    def _load_single(self, location_id: object) -> None:
        _dbg(f"LOAD single location {location_id!r}")

        self._location_id = location_id
        self._location_ids = [location_id]
        self._create_mode = False

        self._set_full_edit_enabled(True)
        self.finalize_btn.hide()
        self.save_btn.show()

        with self._conn() as con:
            loc = con.execute(
                "SELECT * FROM locations WHERE location_id=?",
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
            self.wikidata_edit.setText(loc["wikidata"] or "")

            self.alias_list.clear()
            for r in con.execute(
                "SELECT alias FROM location_aliases WHERE location_id=? ORDER BY alias",
                (location_id,),
            ):
                self.alias_list.addItem(r["alias"])

            gid = con.execute(
                "SELECT group_id FROM location_groups WHERE location_id=?",
                (location_id,),
            ).fetchone()
            self.group_combo.setCurrentIndex(
                self.group_combo.findData(gid["group_id"]) if gid else 0
            )

            rid = con.execute(
                "SELECT region_id FROM location_regions WHERE location_id=?",
                (location_id,),
            ).fetchone()
            self.region_combo.setCurrentIndex(
                self.region_combo.findData(rid["region_id"]) if rid else 0
            )

    def _load_multiple(self, location_ids: Sequence[object]) -> None:
        _dbg(f"LOAD multiple locations count={len(location_ids)}")

        self._location_id = None
        self._location_ids = list(location_ids)
        self._create_mode = False

        self.finalize_btn.hide()
        self.save_btn.show()

        with self._conn() as con:
            rows = list(con.execute(
                "SELECT name FROM locations WHERE location_id IN (%s)"
                % ",".join("?" * len(self._location_ids)),
                self._location_ids,
            ))

            names = {r["name"] for r in rows}
            if len(names) != 1:
                self._set_full_edit_enabled(True)
                QMessageBox.information(
                    self,
                    "Multi-selection not allowed",
                    "Alias editing across multiple locations is only allowed when all selected locations share the same name.",
                )
                return

            self._enter_alias_only_mode()

            self.id_label.setText(f"{len(self._location_ids)} locations")
            self.name_edit.setText(next(iter(names)) or "")

            alias_sets: list[dict[str, str]] = []
            for lid in self._location_ids:
                rows = con.execute(
                    "SELECT normalized, alias FROM location_aliases WHERE location_id=?",
                    (lid,),
                ).fetchall()
                alias_sets.append({r["normalized"]: r["alias"] for r in rows})

            shared = set.intersection(*(set(s.keys()) for s in alias_sets)) if alias_sets else set()

            self.alias_list.clear()
            for norm in sorted(shared):
                self.alias_list.addItem(alias_sets[0][norm])

    # --------------------------------------------------
    # Create mode
    # --------------------------------------------------

    def enter_create_mode(self) -> None:
        self._location_id = None
        self._location_ids = []
        self._create_mode = True

        self._set_full_edit_enabled(True)

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
        if not alias:
            return

        norm = alias.lower()
        for i in range(self.alias_list.count()):
            if self.alias_list.item(i).text().lower() == norm:
                return

        self.alias_list.addItem(alias)
        self.alias_edit.clear()

    def _remove_alias(self) -> None:
        for item in self.alias_list.selectedItems():
            self.alias_list.takeItem(self.alias_list.row(item))

    # --------------------------------------------------
    # Save / create
    # --------------------------------------------------

    def _save_existing(self) -> None:
        if not self._location_ids:
            return

        # ---------------- multi-selection: aliases only
        if len(self._location_ids) > 1:
            with self._conn() as con:
                for lid in self._location_ids:
                    con.execute(
                        "DELETE FROM location_aliases WHERE location_id=?",
                        (lid,),
                    )
                    for i in range(self.alias_list.count()):
                        alias = self.alias_list.item(i).text()
                        con.execute(
                            """
                            INSERT INTO location_aliases
                            (location_id, alias, normalized)
                            VALUES (?, ?, ?)
                            """,
                            (lid, alias, alias.lower()),
                        )

            self.statusMessage.emit(
                f"Aliases updated for {len(self._location_ids)} locations"
            )
            return

        # ---------------- single-selection: full update
        lid = self._location_ids[0]

        with self._conn() as con:
            con.execute(
                """
                UPDATE locations
                SET name=?, place=?, wikidata=?
                WHERE location_id=?
                """,
                (
                    self.name_edit.text() or None,
                    self.place_edit.text() or None,
                    self.wikidata_edit.text() or None,
                    lid,
                ),
            )

            con.execute(
                "DELETE FROM location_aliases WHERE location_id=?",
                (lid,),
            )
            for i in range(self.alias_list.count()):
                alias = self.alias_list.item(i).text()
                con.execute(
                    """
                    INSERT INTO location_aliases
                    (location_id, alias, normalized)
                    VALUES (?, ?, ?)
                    """,
                    (lid, alias, alias.lower()),
                )

            con.execute(
                "DELETE FROM location_groups WHERE location_id=?",
                (lid,),
            )
            con.execute(
                "DELETE FROM location_regions WHERE location_id=?",
                (lid,),
            )

            gid = self.group_combo.currentData()
            rid = self.region_combo.currentData()

            if gid is not None:
                con.execute(
                    "INSERT INTO location_groups VALUES (?, ?)",
                    (lid, gid),
                )
            if rid is not None:
                con.execute(
                    "INSERT INTO location_regions VALUES (?, ?)",
                    (lid, rid),
                )

        self.statusMessage.emit("Location updated")
        self.locationUpdated.emit(lid)

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

                gid = self.group_combo.currentData()
                rid = self.region_combo.currentData()

                if gid is not None:
                    con.execute(
                        "INSERT INTO location_groups VALUES (?, ?)",
                        (location_id, gid),
                    )
                if rid is not None:
                    con.execute(
                        "INSERT INTO location_regions VALUES (?, ?)",
                        (location_id, rid),
                    )

            QMessageBox.information(self, "Created", f"Location {location_id} created")
            self.locationCreated.emit(location_id)

        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Database error", str(e))

    # --------------------------------------------------
    # UI helpers
    # --------------------------------------------------

    def _set_view_mode(self) -> None:
        self._create_mode = False
        self.save_btn.show()
        self.finalize_btn.hide()

    def _set_full_edit_enabled(self, enabled: bool) -> None:
        for w in (
            self.lat_edit,
            self.lon_edit,
            self.name_edit,
            self.place_edit,
            self.wikidata_edit,
            self.group_combo,
            self.region_combo,
        ):
            w.setEnabled(enabled)

    def _enter_alias_only_mode(self) -> None:
        self._set_full_edit_enabled(False)
        self.alias_list.setEnabled(True)
        self.alias_edit.setEnabled(True)
        self.add_alias_btn.setEnabled(True)
        self.remove_alias_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
