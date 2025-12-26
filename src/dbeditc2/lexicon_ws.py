from __future__ import annotations

import sqlite3
import re

from PySide6.QtWidgets import (
    QWidget,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFormLayout,
)

from PySide6.QtCore import Signal

from sitrepc2.config.paths import lexicon_path


# ------------------------------------------------------------
# Holmes validation
# ------------------------------------------------------------

_HOLMES_KEYWORDS = {
    "something",
    "somebody",
    "someone",
    "somewhere",
}


def is_valid_holmes_phrase(text: str) -> bool:
    tokens = re.findall(r"\b\w+\b", text.lower())
    return any(tok in _HOLMES_KEYWORDS for tok in tokens)


# ------------------------------------------------------------
# Lexicon Workspace
# ------------------------------------------------------------

class LexiconWorkspace(QWidget):
    """
    Workspace for editing lexicon phrases.

    - Left column: Event phrases
    - Right column: Context phrases
    """

    statusMessage = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._db_path = lexicon_path()

        # --------------------------------------------------
        # UI columns
        # --------------------------------------------------

        self._event_list = QListWidget(self)
        self._context_list = QListWidget(self)

        # --- Event controls
        self._event_label_edit = QLineEdit(self)
        self._event_phrase_edit = QLineEdit(self)
        self._event_add_btn = QPushButton("Add", self)
        self._event_remove_btn = QPushButton("Remove", self)

        # --- Context controls
        self._context_label_edit = QLineEdit(self)
        self._context_phrase_edit = QLineEdit(self)
        self._context_add_btn = QPushButton("Add", self)
        self._context_remove_btn = QPushButton("Remove", self)

        self._event_add_btn.clicked.connect(
            lambda: self._add_phrase(
                table="event_phrases",
                label_edit=self._event_label_edit,
                phrase_edit=self._event_phrase_edit,
                list_widget=self._event_list,
            )
        )
        self._event_remove_btn.clicked.connect(
            lambda: self._remove_phrase(
                table="event_phrases",
                list_widget=self._event_list,
            )
        )

        self._context_add_btn.clicked.connect(
            lambda: self._add_phrase(
                table="context_phrases",
                label_edit=self._context_label_edit,
                phrase_edit=self._context_phrase_edit,
                list_widget=self._context_list,
            )
        )
        self._context_remove_btn.clicked.connect(
            lambda: self._remove_phrase(
                table="context_phrases",
                list_widget=self._context_list,
            )
        )

        # --------------------------------------------------
        # Layout
        # --------------------------------------------------

        main_layout = QHBoxLayout(self)

        main_layout.addWidget(
            self._build_column(
                title="Event phrases",
                list_widget=self._event_list,
                label_edit=self._event_label_edit,
                phrase_edit=self._event_phrase_edit,
                add_btn=self._event_add_btn,
                remove_btn=self._event_remove_btn,
            ),
            1,
        )

        main_layout.addWidget(
            self._build_column(
                title="Context phrases",
                list_widget=self._context_list,
                label_edit=self._context_label_edit,
                phrase_edit=self._context_phrase_edit,
                add_btn=self._context_add_btn,
                remove_btn=self._context_remove_btn,
            ),
            1,
        )

        # Initial load
        self._load_table("event_phrases", self._event_list)
        self._load_table("context_phrases", self._context_list)

        self.statusMessage.emit("Lexicon workspace ready")

    # --------------------------------------------------
    # UI helpers
    # --------------------------------------------------

    def _build_column(
        self,
        *,
        title: str,
        list_widget: QListWidget,
        label_edit: QLineEdit,
        phrase_edit: QLineEdit,
        add_btn: QPushButton,
        remove_btn: QPushButton,
    ) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel(title))
        layout.addWidget(list_widget)

        form = QFormLayout()
        form.addRow("Label:", label_edit)
        form.addRow("Phrase:", phrase_edit)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(remove_btn)
        layout.addLayout(buttons)

        return container

    # --------------------------------------------------
    # DB operations
    # --------------------------------------------------

    def _load_table(self, table: str, widget: QListWidget) -> None:
        widget.clear()

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()
        cur.execute(f"SELECT label, phrase FROM {table} ORDER BY label;")

        for label, phrase in cur.fetchall():
            item = QListWidgetItem(f"{label}: {phrase}")
            item.setData(0x0100, (label, phrase))
            widget.addItem(item)

        con.close()

    def _add_phrase(
        self,
        *,
        table: str,
        label_edit: QLineEdit,
        phrase_edit: QLineEdit,
        list_widget: QListWidget,
    ) -> None:
        label = label_edit.text().strip()
        phrase = phrase_edit.text().strip()

        if not label or not phrase:
            return

        if not is_valid_holmes_phrase(phrase):
            QMessageBox.critical(
                self,
                "Invalid phrase",
                "Phrase must contain at least one Holmes keyword "
                "(something, somebody, someone, somewhere).",
            )
            return

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()

        cur.execute(
            f"INSERT INTO {table} (label, phrase) VALUES (?, ?);",
            (label, phrase),
        )

        con.commit()
        con.close()

        label_edit.clear()
        phrase_edit.clear()

        self._load_table(table, list_widget)
        self.statusMessage.emit(f"Added phrase to {table}")

    def _remove_phrase(
        self,
        *,
        table: str,
        list_widget: QListWidget,
    ) -> None:
        items = list_widget.selectedItems()
        if not items:
            return

        label, phrase = items[0].data(0x0100)

        con = sqlite3.connect(self._db_path)
        cur = con.cursor()
        cur.execute(
            f"DELETE FROM {table} WHERE label = ? AND phrase = ?;",
            (label, phrase),
        )

        con.commit()
        con.close()

        self._load_table(table, list_widget)
        self.statusMessage.emit(f"Removed phrase from {table}")
