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
)

from PySide6.QtCore import Qt

from sitrepc2.config.paths import gazetteer_path


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


class MainWindow(QMainWindow):
    """
    Alias / ID lookup with alias editing and region display.
    """

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("dbeditc2 — alias editor")

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
        # Location details
        # --------------------------------------------------

        self._details_widget = QWidget(self)
        self._details_layout = QVBoxLayout(self._details_widget)
        self._details_layout.setAlignment(Qt.AlignTop)

        self._detail_labels: dict[str, QLabel] = {}
        for field in ("location_id", "name", "lat", "lon", "place", "wikidata"):
            lbl = QLabel("-", self)
            self._detail_labels[field] = lbl
            self._details_layout.addWidget(lbl)

        # --- Regions display (NEW) ---
        self._details_layout.addWidget(QLabel("Regions:"))
        self._regions_list = QListWidget(self)
        self._regions_list.setMaximumHeight(80)
        self._details_layout.addWidget(self._regions_list)

        # --------------------------------------------------
        # Alias editor
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
        # Layout
        # --------------------------------------------------

        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self._search_edit)
        left_layout.addWidget(self._lookup_mode)
        left_layout.addWidget(self._alias_list)

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.addWidget(left_panel, stretch=1)
        layout.addWidget(self._details_widget, stretch=1)

        self.setCentralWidget(central)

        self._load_by_alias("")

    # --------------------------------------------------
    # Search
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
        self._populate_search_results(rows)

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
            JOIN location_aliases la
              ON la.location_id = l.location_id
            WHERE l.{field} = ?
            ORDER BY la.alias;
            """,
            (value,),
        )

        rows = cur.fetchall()
        con.close()
        self._populate_search_results(rows)

    def _populate_search_results(self, rows) -> None:
        self._alias_list.clear()
        for r in rows:
            item = QListWidgetItem(r["alias"])
            item.setData(Qt.UserRole, r["location_id"])
            self._alias_list.addItem(item)

    # --------------------------------------------------
    # Selection
    # --------------------------------------------------

    def _on_alias_clicked(self, item: QListWidgetItem) -> None:
        self._current_location_id = item.data(Qt.UserRole)
        self._load_location_details()
        self._load_location_regions()   # NEW
        self._load_location_aliases()

    def _load_location_details(self) -> None:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        cur.execute(
            """
            SELECT location_id, name, lat, lon, place, wikidata
            FROM locations
            WHERE location_id = ?;
            """,
            (self._current_location_id,),
        )
        row = cur.fetchone()
        con.close()

        if not row:
            return

        for k in self._detail_labels:
            self._detail_labels[k].setText(f"{k}: {row[k]}")

    # --------------------------------------------------
    # Regions (NEW)
    # --------------------------------------------------

    def _load_location_regions(self) -> None:
        self._regions_list.clear()

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()

        cur.execute(
            """
            SELECT r.name
            FROM location_regions lr
            JOIN regions r
              ON r.region_id = lr.region_id
            WHERE lr.location_id = ?
            ORDER BY r.name;
            """,
            (self._current_location_id,),
        )

        for (name,) in cur.fetchall():
            self._regions_list.addItem(name)

        con.close()

    # --------------------------------------------------
    # Aliases
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
