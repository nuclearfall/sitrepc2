from __future__ import annotations

import sqlite3
from typing import Set

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

        # ---- selection state ----
        self._selected_location_ids: Set[int] = set()

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
        self._alias_list.setSelectionMode(QListWidget.ExtendedSelection)
        self._alias_list.itemSelectionChanged.connect(self._on_alias_selection_changed)

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
        self._save_btn.clicked.connect(self._save_location_changes)
        self._details_layout.addWidget(self._save_btn)

        # --------------------------------------------------
        # Alias editor (single + multi select)
        # --------------------------------------------------

        self._details_layout.addWidget(QLabel("Aliases for selected location(s):"))

        self._location_aliases = QListWidget(self)
        self._location_aliases.setSelectionMode(QListWidget.SingleSelection)
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

        self._set_details_enabled(False)
        self._load_by_alias("")

    # --------------------------------------------------
    # Search
    # --------------------------------------------------

    def _on_search_changed(self, text: str) -> None:
        # Clearing/refreshing search results should also clear selection state
        # because selected items might no longer exist.
        self._alias_list.blockSignals(True)
        try:
            self._alias_list.clearSelection()
        finally:
            self._alias_list.blockSignals(False)

        self._selected_location_ids.clear()
        self._clear_location_details()
        self._set_details_enabled(False)
        self._location_aliases.clear()

        if self._lookup_mode.currentText() == "alias":
            self._load_by_alias(text)
        else:
            self._load_by_location_field(self._lookup_mode.currentText(), text)

    def _load_by_alias(self, text: str) -> None:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        if text:
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
        else:
            cur.execute(
                "SELECT location_id, alias FROM location_aliases ORDER BY alias LIMIT 200;"
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
            ORDER BY la.alias
            LIMIT 200;
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
    # Selection handling
    # --------------------------------------------------

    def _on_alias_selection_changed(self) -> None:
        items = self._alias_list.selectedItems()
        self._selected_location_ids = {int(i.data(Qt.UserRole)) for i in items}

        self._refresh_right_panel()

        self.statusBar().showMessage(f"{len(self._selected_location_ids)} location(s) selected")

    def _refresh_right_panel(self) -> None:
        """
        Refresh details + alias editor based on current selection.
        """
        self._location_aliases.clear()

        if len(self._selected_location_ids) == 1:
            loc_id = next(iter(self._selected_location_ids))
            self._load_location(loc_id)
            self._set_details_enabled(True)
            self._load_location_aliases_single(loc_id)   # clears + reloads
            return

        # Multi-select (or none): details blank/disabled, alias editor shows COMMON aliases
        self._clear_location_details()
        self._set_details_enabled(False)

        if len(self._selected_location_ids) >= 2:
            self._load_common_aliases_for_selection()

    # --------------------------------------------------
    # Location loading
    # --------------------------------------------------

    def _load_location(self, location_id: int) -> None:
        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        cur.execute(
            """
            SELECT location_id, lat, lon, name, place, wikidata
            FROM locations
            WHERE location_id = ?;
            """,
            (location_id,),
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
            (location_id,),
        )
        region_row = cur.fetchone()
        con.close()

        if not row:
            return

        self._lbl_location_id.setText(str(row["location_id"]))
        self._lbl_lat.setText(str(row["lat"]))
        self._lbl_lon.setText(str(row["lon"]))
        self._edit_name.setText(row["name"] or "")
        self._edit_place.setText(row["place"] or "")
        self._edit_wikidata.setText(row["wikidata"] or "")
        self._lbl_region.setText(region_row["name"] if region_row else "-")

    # --------------------------------------------------
    # Alias list population
    # --------------------------------------------------

    def _load_location_aliases_single(self, location_id: int) -> None:
        """
        Load ALL aliases for a single location.
        Always clears first to avoid duplicates.
        """
        self._location_aliases.clear()

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()
        cur.execute(
            "SELECT alias FROM location_aliases WHERE location_id = ? ORDER BY alias;",
            (location_id,),
        )
        for (alias,) in cur.fetchall():
            self._location_aliases.addItem(alias)
        con.close()

    def _load_common_aliases_for_selection(self) -> None:
        """
        Load aliases COMMON to all selected locations.
        This makes multi-remove well-defined and usable.

        We display `normalized` because it is the canonical key used by deletion logic.
        """
        self._location_aliases.clear()

        ids = sorted(self._selected_location_ids)
        if not ids:
            return

        placeholders = ",".join("?" for _ in ids)

        con = sqlite3.connect(self._db_path)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # Use normalized as the identity across locations
        cur.execute(
            f"""
            SELECT normalized
            FROM location_aliases
            WHERE location_id IN ({placeholders})
            GROUP BY normalized
            HAVING COUNT(DISTINCT location_id) = ?
            ORDER BY normalized;
            """,
            (*ids, len(ids)),
        )

        rows = cur.fetchall()
        con.close()

        for r in rows:
            # display normalized (stable + matches deletion key)
            self._location_aliases.addItem(r["normalized"])

    # --------------------------------------------------
    # Alias editing (single + multi)
    # --------------------------------------------------

    def _add_alias(self) -> None:
        if not self._selected_location_ids:
            return

        alias = self._alias_input.text().strip()
        if not alias:
            return

        norm = normalize(alias)

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()

        for loc_id in self._selected_location_ids:
            cur.execute(
                """
                INSERT OR IGNORE INTO location_aliases
                    (location_id, alias, normalized)
                VALUES (?, ?, ?);
                """,
                (loc_id, alias, norm),
            )

        con.commit()
        con.close()

        self._alias_input.clear()
        self._refresh_alias_editor_after_write()

        self.statusBar().showMessage(f"Alias added to {len(self._selected_location_ids)} location(s)")

    def _remove_alias(self) -> None:
        if not self._selected_location_ids:
            return

        items = self._location_aliases.selectedItems()
        if not items:
            return

        # IMPORTANT:
        # - In single-select mode, items are raw aliases -> normalize them.
        # - In multi-select mode, items are already normalized.
        selected_text = items[0].text()
        norm = normalize(selected_text)

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()

        for loc_id in self._selected_location_ids:
            cur.execute(
                """
                DELETE FROM location_aliases
                WHERE location_id = ?
                  AND normalized = ?;
                """,
                (loc_id, norm),
            )

        con.commit()
        con.close()

        self._refresh_alias_editor_after_write()

        self.statusBar().showMessage(f"Alias removed from {len(self._selected_location_ids)} location(s)")

    def _refresh_alias_editor_after_write(self) -> None:
        """
        Refresh alias list panel without duplicating UI items.
        """
        if len(self._selected_location_ids) == 1:
            loc_id = next(iter(self._selected_location_ids))
            self._load_location_aliases_single(loc_id)
        elif len(self._selected_location_ids) >= 2:
            self._load_common_aliases_for_selection()
        else:
            self._location_aliases.clear()

    # --------------------------------------------------
    # Save (single-location only)
    # --------------------------------------------------

    def _save_location_changes(self) -> None:
        if len(self._selected_location_ids) != 1:
            return

        location_id = next(iter(self._selected_location_ids))

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()

        cur.execute(
            """
            UPDATE locations
            SET name = ?, place = ?, wikidata = ?
            WHERE location_id = ?;
            """,
            (
                self._edit_name.text().strip() or None,
                self._edit_place.text().strip() or None,
                self._edit_wikidata.text().strip() or None,
                location_id,
            ),
        )

        if cur.rowcount != 1:
            con.rollback()
            con.close()
            raise RuntimeError("Location update affected unexpected row count")

        con.commit()
        con.close()

        self._load_location(location_id)
        self.statusBar().showMessage(f"Saved location {location_id}")

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _clear_location_details(self) -> None:
        self._lbl_location_id.setText("-")
        self._lbl_lat.setText("-")
        self._lbl_lon.setText("-")
        self._edit_name.clear()
        self._edit_place.clear()
        self._edit_wikidata.clear()
        self._lbl_region.setText("-")

    def _set_details_enabled(self, enabled: bool) -> None:
        for w in (self._edit_name, self._edit_place, self._edit_wikidata, self._save_btn):
            w.setEnabled(enabled)
