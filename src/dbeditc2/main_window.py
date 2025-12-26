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
    QPushButton,
    QComboBox,
    QFormLayout,
)

from PySide6.QtCore import Qt

from sitrepc2.config.paths import gazetteer_path


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("dbeditc2 — alias & location editor")
        self._db_path = gazetteer_path()
        self._current_location_id: int | None = None

        # --------------------------------------------------
        # Search widgets
        # --------------------------------------------------

        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText("Search…")
        self._search_edit.textChanged.connect(self._on_search_changed)

        self._lookup_mode = QComboBox(self)
        self._lookup_mode.addItems(["alias", "osm_id", "wikidata"])
        self._lookup_mode.currentTextChanged.connect(
            lambda _: self._on_search_changed(self._search_edit.text())
        )

        self._alias_list = QListWidget(self)
        self._alias_list.itemClicked.connect(self._on_alias_clicked)

        # --------------------------------------------------
        # Details form
        # --------------------------------------------------

        self._details_widget = QWidget(self)
        self._details_layout = QVBoxLayout(self._details_widget)
        self._details_layout.setAlignment(Qt.AlignTop)

        form = QFormLayout()
        self._details_layout.addLayout(form)

        self._lbl_location_id = QLabel("-")
        self._lbl_lat = QLabel("-")
        self._lbl_lon = QLabel("-")
        self._lbl_region = QLabel("-")

        self._edit_name = QLineEdit()
        self._edit_place = QLineEdit()
        self._edit_wikidata = QLineEdit()

        form.addRow("Location ID:", self._lbl_location_id)
        form.addRow("Latitude:", self._lbl_lat)
        form.addRow("Longitude:", self._lbl_lon)
        form.addRow("Name:", self._edit_name)
        form.addRow("Place:", self._edit_place)
        form.addRow("Wikidata:", self._edit_wikidata)
        form.addRow("Region:", self._lbl_region)

        self._save_btn = QPushButton("Save location changes", self)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_location_changes)
        self._details_layout.addWidget(self._save_btn)

        # --------------------------------------------------
        # Alias editor for selected location
        # --------------------------------------------------

        self._details_layout.addWidget(QLabel("Aliases for this location:"))

        self._location_aliases = QListWidget(self)
        self._details_layout.addWidget(self._location_aliases)

        alias_controls = QHBoxLayout()
        self._alias_input = QLineEdit(self)
        self._alias_input.setPlaceholderText("Add alias…")
        self._alias_add_btn = QPushButton("Add", self)
        self._alias_remove_btn = QPushButton("Remove", self)

        alias_controls.addWidget(self._alias_input)
        alias_controls.addWidget(self._alias_add_btn)
        alias_controls.addWidget(self._alias_remove_btn)
        self._details_layout.addLayout(alias_controls)

        self._alias_add_btn.clicked.connect(self._add_alias)
        self._alias_remove_btn.clicked.connect(self._remove_alias)

        # --------------------------------------------------
        # Layout wiring
        # --------------------------------------------------

        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self._search_edit)
        left_layout.addWidget(self._lookup_mode)
        left_layout.addWidget(self._alias_list)

        central = QWidget(self)
        main_layout = QHBoxLayout(central)
        main_layout.addWidget(left, 1)
        main_layout.addWidget(self._details_widget, 1)
        self.setCentralWidget(central)

        self.statusBar().showMessage("Ready")

        self._load_by_alias("")

    # --------------------------------------------------
    # Search logic
    # --------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        mode = self._lookup_mode.currentText()
        if mode == "alias":
            self._load_by_alias(text)
        else:
            self._load_by_location_field(mode, text)

    def _load_by_alias(self, text: str) -> None:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        if not text:
            cur.execute(
                "SELECT location_id, alias FROM location_aliases ORDER BY alias LIMIT 200;"
            )
        else:
            cur.execute(
                """
                SELECT location_id, alias
                FROM location_aliases
                WHERE normalized LIKE ?
                ORDER BY alias
                LIMIT 200;
                """,
                (f"{normalize(text)}%",),
            )

        rows = cur.fetchall()
        con.close()

        self._alias_list.clear()
        for r in rows:
            item = QListWidgetItem(r["alias"])
            item.setData(Qt.UserRole, int(r["location_id"]))
            self._alias_list.addItem(item)

    def _load_by_location_field(self, field: str, value: str) -> None:
        if not value:
            self._alias_list.clear()
            return

        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        cur.execute(
            f"""
            SELECT la.location_id, la.alias
            FROM locations l
            JOIN location_aliases la ON la.location_id = l.location_id
            WHERE l.{field} = ?
            ORDER BY la.alias;
            """,
            (value,),
        )

        rows = cur.fetchall()
        con.close()

        self._alias_list.clear()
        for r in rows:
            item = QListWidgetItem(r["alias"])
            item.setData(Qt.UserRole, int(r["location_id"]))
            self._alias_list.addItem(item)

    # --------------------------------------------------
    # Selection + details
    # --------------------------------------------------

    def _on_alias_clicked(self, item: QListWidgetItem) -> None:
        location_id = item.data(Qt.UserRole)
        self._current_location_id = location_id
        self._load_location()
        self._load_location_aliases()
        self._save_btn.setEnabled(True)

    def _load_location(self) -> None:
        if self._current_location_id is None:
            return

        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        cur.execute(
            """
            SELECT location_id, lat, lon, name, place, wikidata
            FROM locations
            WHERE location_id = ?;
            """,
            (self._current_location_id,),
        )
        row = cur.fetchone()

        cur.execute(
            """
            SELECT r.name
            FROM location_regions lr
            JOIN regions r ON r.region_id = lr.region_id
            WHERE lr.location_id = ?
            LIMIT 1;
            """,
            (self._current_location_id,),
        )
        region_row = cur.fetchone()

        con.close()

        if not row:
            return

        # Populate form
        self._lbl_location_id.setText(str(row["location_id"]))
        self._lbl_lat.setText(str(row["lat"]))
        self._lbl_lon.setText(str(row["lon"]))
        self._edit_name.setText(row["name"] or "")
        self._edit_place.setText(row["place"] or "")
        self._edit_wikidata.setText(row["wikidata"] or "")
        self._lbl_region.setText(region_row["name"] if region_row else "-")

    # --------------------------------------------------
    # Alias list for this location
    # --------------------------------------------------

    def _load_location_aliases(self) -> None:
        self._location_aliases.clear()

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()
        cur.execute(
            "SELECT alias FROM location_aliases WHERE location_id = ? ORDER BY alias;",
            (self._current_location_id,),
        )
        for (alias,) in cur.fetchall():
            self._location_aliases.addItem(alias)

        con.close()

    # --------------------------------------------------
    # Alias editing
    # --------------------------------------------------

    def _add_alias(self) -> None:
        if not self._current_location_id:
            return

        alias = self._alias_input.text().strip()
        if not alias:
            return

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO location_aliases
                (location_id, alias, normalized)
            VALUES (?, ?, ?);
            """,
            (self._current_location_id, alias, normalize(alias)),
        )
        con.commit()
        con.close()

        self._alias_input.clear()
        self._load_location_aliases()

    def _remove_alias(self) -> None:
        if not self._current_location_id:
            return

        items = self._location_aliases.selectedItems()
        if not items:
            return

        alias = items[0].text()

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()
        cur.execute(
            """
            DELETE FROM location_aliases
            WHERE location_id = ?
              AND normalized = ?;
            """,
            (self._current_location_id, normalize(alias)),
        )
        con.commit()
        con.close()

        self._load_location_aliases()

    # --------------------------------------------------
    # Save details
    # --------------------------------------------------

    def _save_location_changes(self) -> None:
        if self._current_location_id is None:
            return

        new_name = self._edit_name.text().strip() or None
        new_place = self._edit_place.text().strip() or None
        new_wikidata = self._edit_wikidata.text().strip() or None

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()

        cur.execute(
            """
            UPDATE locations
            SET name = ?, place = ?, wikidata = ?
            WHERE location_id = ?;
            """,
            (new_name, new_place, new_wikidata, self._current_location_id),
        )

        if cur.rowcount != 1:
            con.rollback()
            con.close()
            raise RuntimeError(
                f"Failed to update exactly one row for location_id={self._current_location_id}"
            )

        con.commit()
        con.close()

        # Reload to reflect canonical saved state
        self._load_location()

        # Defocus edits
        self._edit_name.clearFocus()
        self._edit_place.clearFocus()
        self._edit_wikidata.clearFocus()

        self.statusBar().showMessage(
            f"Saved details for location_id={self._current_location_id}"
        )
