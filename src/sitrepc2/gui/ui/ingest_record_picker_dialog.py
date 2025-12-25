# gui/ui/ingest_record_picker_dialog.py
from __future__ import annotations

import sqlite3
from typing import List

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
)

from sitrepc2.config.paths import records_path


class IngestRecordPickerDialog(QDialog):
    """
    Dialog for selecting ingest records from records.db.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Load Ingest Text")
        self.resize(700, 400)

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(
            QListWidget.ExtendedSelection
        )
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_records()

    # ------------------------------------------------------------------

    def _load_records(self) -> None:
        con = sqlite3.connect(records_path())
        con.row_factory = sqlite3.Row

        rows = con.execute(
            """
            SELECT id, source, published_at, text
            FROM ingest_posts
            ORDER BY published_at DESC
            """
        ).fetchall()

        for row in rows:
            label = (
                f"[{row['published_at']}] "
                f"{row['source']} — {row['text'][:80]}…"
            )
            item = QListWidgetItem(label)
            item.setData(0x0100, row["text"])  # Qt.UserRole
            self.list_widget.addItem(item)

        con.close()

    # ------------------------------------------------------------------

    def selected_texts(self) -> List[str]:
        texts: List[str] = []

        for item in self.list_widget.selectedItems():
            text = item.data(0x0100)
            if isinstance(text, str):
                texts.append(text)

        return texts
