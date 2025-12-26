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

        self.setWindowTitle("dbeditc2 — location editor")
        self._db_path = gazetteer_path()
        self._current_location_id: int | None = None

        # --------------------------------------------------
        # Search
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

        self._save_btn = QPushButton("Save changes", self)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_location_changes)
        self._details_layout.addWidget(self._save_btn)

        # --------------------------------------------------
        # Layout
        # --------------------------------------------------

        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self._search_edit)
        left_layout.addWidget(self._lookup_mode)
        left_layout.addWidget(self._alias_list)

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.addWidget(left, 1)
        layout.addWidget(self._details_widget, 1)
        self.setCentralWidget(central)

        # Ensure status bar exists
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
            # Force Python int (avoid QVariant surprises)
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
    # Selection
    # --------------------------------------------------

    def _on_alias_clicked(self, item: QListWidgetItem) -> None:
        raw_id = item.data(Qt.UserRole)
        try:
            self._current_location_id = int(raw_id)
        except Exception as e:
            raise RuntimeError(f"Selected location_id is not an int: {raw_id!r}") from e

        self._load_location()
        self._save_btn.setEnabled(True)
        self.statusBar().showMessage(f"Loaded location_id={self._current_location_id}")

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
            raise RuntimeError(f"locations row not found for location_id={self._current_location_id}")

        self._lbl_location_id.setText(str(row["location_id"]))
        self._lbl_lat.setText(str(row["lat"]))
        self._lbl_lon.setText(str(row["lon"]))
        self._edit_name.setText(row["name"] or "")
        self._edit_place.setText(row["place"] or "")
        self._edit_wikidata.setText(row["wikidata"] or "")
        self._lbl_region.setText(region_row["name"] if region_row else "-")

    # --------------------------------------------------
    # Save
    # --------------------------------------------------

    def _save_location_changes(self) -> None:
        if self._current_location_id is None:
            raise RuntimeError("Save requested with no selected location")

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
            (new_name, new_place, new_wikidata, int(self._current_location_id)),
        )

        # FAIL LOUDLY: must touch exactly one row.
        # If this is >1, something is catastrophically wrong (or triggers exist).
        if cur.rowcount != 1:
            con.rollback()
            con.close()
            raise RuntimeError(
                f"Unexpected UPDATE rowcount={cur.rowcount} for location_id={self._current_location_id}. "
                "Refusing to commit."
            )

        con.commit()
        con.close()

        # Feedback: reload canonical DB state, then defocus edits
        self._load_location()
        self._save_btn.setFocus(Qt.OtherFocusReason)  # defocus text fields
        self.statusBar().showMessage(f"Saved changes for location_id={self._current_location_id}")
