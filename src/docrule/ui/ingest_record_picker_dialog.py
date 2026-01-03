from __future__ import annotations

import sqlite3
from typing import List, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QDateEdit,
)

from sitrepc2.config.paths import records_path


USER_ROLE = Qt.UserRole


class IngestRecordPickerDialog(QDialog):
    """
    Dialog for selecting ingest records from records.db,
    with basic filtering support.
    """

    # ------------------------------------------------------------------

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Load Ingest Text")
        self.resize(900, 500)

        root = QVBoxLayout(self)

        # --------------------------------------------------------------
        # Filters
        # --------------------------------------------------------------

        filter_layout = QHBoxLayout()

        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        self.from_date.setSpecialValueText("From…")
        self.from_date.setDate(self.from_date.minimumDate())

        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("yyyy-MM-dd")
        self.to_date.setSpecialValueText("To…")
        self.to_date.setDate(self.to_date.maximumDate())

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("source (telegram, x, web…)")

        self.publisher_edit = QLineEdit()
        self.publisher_edit.setPlaceholderText("publisher")

        self.alias_edit = QLineEdit()
        self.alias_edit.setPlaceholderText("alias")

        self.lang_edit = QLineEdit()
        self.lang_edit.setPlaceholderText("lang")

        apply_btn = QPushButton("Apply Filters")
        apply_btn.clicked.connect(self._load_records)

        for w in (
            QLabel("From:"),
            self.from_date,
            QLabel("To:"),
            self.to_date,
            self.source_edit,
            self.publisher_edit,
            self.alias_edit,
            self.lang_edit,
            apply_btn,
        ):
            filter_layout.addWidget(w)

        root.addLayout(filter_layout)

        # --------------------------------------------------------------
        # Record list
        # --------------------------------------------------------------

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        root.addWidget(self.list_widget)

        # --------------------------------------------------------------
        # Buttons
        # --------------------------------------------------------------

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._load_records()

    # ------------------------------------------------------------------
    # Query / loading
    # ------------------------------------------------------------------

    def _build_query(self) -> tuple[str, Dict[str, Any]]:
        """
        Build SQL WHERE clause and parameter dict from UI state.
        """
        where = []
        params: Dict[str, Any] = {}

        if self.from_date.date().isValid():
            where.append("published_at >= :from_date")
            params["from_date"] = (
                self.from_date.date().toString("yyyy-MM-dd")
            )

        if self.to_date.date().isValid():
            where.append("published_at <= :to_date")
            params["to_date"] = (
                self.to_date.date().toString("yyyy-MM-dd") + "T23:59:59"
            )

        if self.source_edit.text().strip():
            where.append("source = :source")
            params["source"] = self.source_edit.text().strip()

        if self.publisher_edit.text().strip():
            where.append("publisher LIKE :publisher")
            params["publisher"] = f"%{self.publisher_edit.text().strip()}%"

        if self.alias_edit.text().strip():
            where.append("alias LIKE :alias")
            params["alias"] = f"%{self.alias_edit.text().strip()}%"

        if self.lang_edit.text().strip():
            where.append("lang = :lang")
            params["lang"] = self.lang_edit.text().strip()

        where_sql = ""
        if where:
            where_sql = "WHERE " + " AND ".join(where)

        sql = f"""
            SELECT
                id,
                source,
                publisher,
                alias,
                lang,
                published_at,
                text
            FROM ingest_posts
            {where_sql}
            ORDER BY published_at DESC
        """

        return sql, params

    # ------------------------------------------------------------------

    def _load_records(self) -> None:
        self.list_widget.clear()

        con = sqlite3.connect(records_path())
        con.row_factory = sqlite3.Row

        sql, params = self._build_query()

        rows = con.execute(sql, params).fetchall()

        for row in rows:
            label = (
                f"[{row['published_at']}] "
                f"{row['alias']} / {row['source']} — "
                f"{row['text'][:80]}…"
            )

            item = QListWidgetItem(label)
            item.setData(USER_ROLE, row["text"])
            self.list_widget.addItem(item)

        con.close()

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def selected_texts(self) -> List[str]:
        texts: List[str] = []

        for item in self.list_widget.selectedItems():
            text = item.data(USER_ROLE)
            if isinstance(text, str):
                texts.append(text)

        return texts
