from __future__ import annotations

import sqlite3
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QComboBox,
    QFormLayout,
    QPlainTextEdit,
    QMessageBox,
)

from sitrepc2.config.paths import gazetteer_path


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _split_aliases(text: str) -> List[str]:
    raw = text.replace(",", "\n").replace(";", "\n")
    return sorted({a.strip() for a in raw.splitlines() if a.strip()})


# ------------------------------------------------------------
# Gazetteer Workspace
# ------------------------------------------------------------

class GazetteerWorkspace(QWidget):
    statusMessage = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._db_path = gazetteer_path()
        self._current_location_id: Optional[int] = None
        self._create_mode: bool = False

        # --------------------------------------------------
        # Search pane
        # --------------------------------------------------

        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Search locations…")
        self._search_edit.textChanged.connect(self._search)

        self._add_new_btn = QPushButton("Add New", self)
        self._add_new_btn.clicked.connect(self._enter_create_mode)

        self._result_list = QListWidget(self)
        self._result_list.itemSelectionChanged.connect(self._on_select)

        search_layout = QVBoxLayout()
        search_layout.addWidget(self._search_edit)
        search_layout.addWidget(self._add_new_btn)
        search_layout.addWidget(self._result_list)

        # --------------------------------------------------
        # Detail / form pane
        # --------------------------------------------------

        self._name_edit = QLineEdit(self)
        self._place_edit = QLineEdit(self)
        self._lat_edit = QLineEdit(self)
        self._lon_edit = QLineEdit(self)

        self._aliases_edit = QPlainTextEdit(self)
        self._aliases_edit.setPlaceholderText(
            "One alias per line, or comma / semicolon separated"
        )

        self._groups_list = QListWidget(self)
        self._groups_list.setSelectionMode(QListWidget.MultiSelection)

        self._regions_list = QListWidget(self)
        self._regions_list.setSelectionMode(QListWidget.MultiSelection)

        self._finalize_btn = QPushButton("Finalize Entry", self)
        self._finalize_btn.clicked.connect(self._finalize_entry)
        self._finalize_btn.hide()

        form = QFormLayout()
        form.addRow("Name", self._name_edit)
        form.addRow("Place", self._place_edit)
        form.addRow("Latitude", self._lat_edit)
        form.addRow("Longitude", self._lon_edit)
        form.addRow("Aliases", self._aliases_edit)
        form.addRow("Groups", self._groups_list)
        form.addRow("Regions", self._regions_list)
        form.addRow(self._finalize_btn)

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

    # --------------------------------------------------
    # Data loading
    # --------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    def _load_groups(self) -> None:
        self._groups_list.clear()
        with self._conn() as con:
            for r in con.execute("SELECT group_id, name FROM groups ORDER BY name"):
                item = QListWidgetItem(r["name"])
                item.setData(Qt.UserRole, r["group_id"])
                self._groups_list.addItem(item)

    def _load_regions(self) -> None:
        self._regions_list.clear()
        with self._conn() as con:
            for r in con.execute("SELECT region_id, name FROM regions ORDER BY name"):
                item = QListWidgetItem(r["name"])
                item.setData(Qt.UserRole, r["region_id"])
                self._regions_list.addItem(item)

    # --------------------------------------------------
    # Search / select
    # --------------------------------------------------

    def _search(self, text: str) -> None:
        self._result_list.clear()
        with self._conn() as con:
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
                item.setData(Qt.UserRole, r["location_id"])
                self._result_list.addItem(item)

    def _on_select(self) -> None:
        if not self._result_list.selectedItems():
            return

        self._create_mode = False
        self._finalize_btn.hide()

        item = self._result_list.selectedItems()[0]
        self._current_location_id = item.data(Qt.UserRole)

        self._load_location(self._current_location_id)

    # --------------------------------------------------
    # Create mode
    # --------------------------------------------------

    def _enter_create_mode(self) -> None:
        self._create_mode = True
        self._current_location_id = None
        self._result_list.clearSelection()

        self._name_edit.clear()
        self._place_edit.clear()
        self._lat_edit.clear()
        self._lon_edit.clear()
        self._aliases_edit.clear()

        for w in (self._groups_list, self._regions_list):
            for i in range(w.count()):
                w.item(i).setSelected(False)

        self._finalize_btn.show()

    # --------------------------------------------------
    # Load existing location
    # --------------------------------------------------

    def _load_location(self, location_id: int) -> None:
        with self._conn() as con:
            loc = con.execute(
                "SELECT * FROM locations WHERE location_id = ?", (location_id,)
            ).fetchone()

            self._name_edit.setText(loc["name"] or "")
            self._place_edit.setText(loc["place"] or "")
            self._lat_edit.setText(str(loc["lat"]))
            self._lon_edit.setText(str(loc["lon"]))

            aliases = con.execute(
                "SELECT alias FROM location_aliases WHERE location_id = ?",
                (location_id,),
            )
            self._aliases_edit.setPlainText("\n".join(a["alias"] for a in aliases))

    # --------------------------------------------------
    # Finalize creation
    # --------------------------------------------------

    def _finalize_entry(self) -> None:
        try:
            lat = float(self._lat_edit.text())
            lon = float(self._lon_edit.text())
        except ValueError:
            QMessageBox.critical(self, "Invalid input", "Latitude/Longitude invalid.")
            return

        aliases = _split_aliases(self._aliases_edit.toPlainText())

        try:
            with self._conn() as con:
                cur = con.execute(
                    """
                    INSERT INTO locations (lat, lon, name, place)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        lat,
                        lon,
                        self._name_edit.text() or None,
                        self._place_edit.text() or None,
                    ),
                )
                loc_id = cur.lastrowid

                for a in aliases:
                    con.execute(
                        """
                        INSERT INTO location_aliases (location_id, alias, normalized)
                        VALUES (?, ?, ?)
                        """,
                        (loc_id, a, a.lower()),
                    )

                for item in self._groups_list.selectedItems():
                    con.execute(
                        """
                        INSERT INTO location_groups (location_id, group_id)
                        VALUES (?, ?)
                        """,
                        (loc_id, item.data(Qt.UserRole)),
                    )

                for item in self._regions_list.selectedItems():
                    con.execute(
                        """
                        INSERT INTO location_regions (location_id, region_id)
                        VALUES (?, ?)
                        """,
                        (loc_id, item.data(Qt.UserRole)),
                    )

            self.statusMessage.emit(f"Created location {loc_id}")
            self._create_mode = False
            self._finalize_btn.hide()
            self._search(self._search_edit.text())

        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Database error", str(e))
