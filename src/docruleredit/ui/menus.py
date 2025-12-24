from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QFileDialog, QMessageBox

from ..io.text_loader import load_text_file
from ..io.json_loader import load_json_text
from ..io.csv_loader import load_csv_text


class MenuActions:
    """
    Encapsulates File/Edit menu behavior.

    This class wires menu actions to loader logic and delegates
    document replacement to the MainWindow.
    """

    def __init__(self, main_window) -> None:
        self.main = main_window
        self._wire_actions()

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def _wire_actions(self) -> None:
        self.main.open_text_action.triggered.connect(self._open_text)
        self.main.open_json_action.triggered.connect(self._open_json)
        self.main.open_csv_action.triggered.connect(self._open_csv)

        self.main.open_rulers_action.triggered.connect(
            self.main.load_rulers
        )
        self.main.save_rulers_action.triggered.connect(
            self.main.save_rulers
        )

        self.main.copy_action.triggered.connect(
            self.main.centralWidget().copy
        )
        self.main.cut_action.triggered.connect(
            self.main.centralWidget().cut
        )
        self.main.paste_action.triggered.connect(
            self.main.centralWidget().paste
        )

    # ------------------------------------------------------------------
    # File open handlers
    # ------------------------------------------------------------------

    def _open_text(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.main, "Open Text File"
        )
        if not path:
            return

        try:
            text = load_text_file(Path(path))
        except Exception as exc:
            self._error(str(exc))
            return

        self.main.load_text(text)

    def _open_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.main, "Open JSON / JSONL File"
        )
        if not path:
            return

        key, ok = self.main.prompt_text(
            "JSON Key",
            "Enter the JSON field containing text:",
        )
        if not ok or not key:
            return

        try:
            text = load_json_text(Path(path), key)
        except Exception as exc:
            self._error(str(exc))
            return

        self.main.load_text(text)

    def _open_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.main, "Open CSV File"
        )
        if not path:
            return

        column, ok = self.main.prompt_text(
            "CSV Column",
            "Enter the column header containing text:",
        )
        if not ok or not column:
            return

        delimiter, ok = self.main.prompt_text(
            "CSV Delimiter (Optional)",
            "Enter delimiter (leave blank to auto-detect):",
        )
        delimiter = delimiter or None

        try:
            text = load_csv_text(Path(path), column, delimiter)
        except Exception as exc:
            self._error(str(exc))
            return

        self.main.load_text(text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _error(self, message: str) -> None:
        QMessageBox.critical(
            self.main,
            "Error",
            message,
        )
