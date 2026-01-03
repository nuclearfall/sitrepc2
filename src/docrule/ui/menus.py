from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from ..io.open_path import open_path, NeedsUserInput


class MenuActions:
    """
    File / Edit menu wiring.
    """

    def __init__(self, main_window) -> None:
        self.main = main_window
        self._wire_actions()

    # ------------------------------------------------------------------

    def _wire_actions(self) -> None:
        m = self.main

        m.open_text_action.triggered.connect(self._open_file)
        m.open_rulers_action.triggered.connect(m.load_rulers)
        m.save_rulers_action.triggered.connect(m.save_rulers)

        m.copy_action.triggered.connect(self._copy)
        m.cut_action.triggered.connect(self._cut)
        m.paste_action.triggered.connect(self._paste)

    # ------------------------------------------------------------------
    # File open
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.main,
            "Open File",
            "",
            "All Files (*);;Text (*.txt);;JSON (*.json *.jsonl);;CSV (*.csv)",
        )

        if not path:
            return

        path = Path(path)

        try:
            text = open_path(path)
        except NeedsUserInput:
            self._prompt_for_field(path)
            return
        except Exception as exc:
            self._error(str(exc))
            return

        self.main.load_text(text)

    def _prompt_for_field(self, path: Path) -> None:
        suffix = path.suffix.lower()

        if suffix in {".json", ".jsonl"}:
            key, ok = self.main.prompt_text(
                "JSON Field Required",
                "Enter the JSON field containing text:",
            )
            if not ok or not key:
                return

            text = open_path(path, json_key=key)

        elif suffix == ".csv":
            column, ok = self.main.prompt_text(
                "CSV Column Required",
                "Enter the CSV column containing text:",
            )
            if not ok or not column:
                return

            text = open_path(path, csv_column=column)

        else:
            self._error("Unsupported file type")
            return

        self.main.load_text(text)

    # ------------------------------------------------------------------
    # Clipboard (viewer-agnostic)
    # ------------------------------------------------------------------

    def _copy(self) -> None:
        w = self.main.centralWidget()
        if hasattr(w, "page"):
            w.page().triggerAction(w.page().Copy)

    def _cut(self) -> None:
        w = self.main.centralWidget()
        if hasattr(w, "page"):
            w.page().triggerAction(w.page().Cut)

    def _paste(self) -> None:
        w = self.main.centralWidget()
        if hasattr(w, "page"):
            w.page().triggerAction(w.page().Paste)

    # ------------------------------------------------------------------

    def _error(self, msg: str) -> None:
        QMessageBox.critical(self.main, "Error", msg)
