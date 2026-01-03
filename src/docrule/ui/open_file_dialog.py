from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QFileDialog,
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
)

from ..io.open_path import OpenRequest


class OpenFileDialog(QFileDialog):
    """
    Professional file-open dialog with conditional metadata fields.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # REQUIRED: otherwise layout() is None on macOS/Windows
        self.setOption(QFileDialog.DontUseNativeDialog, True)

        self.setWindowTitle("Open File")
        self.setFileMode(QFileDialog.ExistingFile)
        self.setNameFilters(
            [
                "Text (*.txt)",
                "JSON / JSONL (*.json *.jsonl)",
                "CSV (*.csv)",
                "All Files (*)",
            ]
        )

        # ---- Metadata fields ----
        self._json_key = QLineEdit()
        self._csv_column = QLineEdit()
        self._csv_delimiter = QLineEdit()

        self._json_key.setPlaceholderText("JSON field containing text")
        self._csv_column.setPlaceholderText("CSV column containing text")
        self._csv_delimiter.setPlaceholderText("Delimiter (optional)")

        # ---- Metadata container ----
        meta = QWidget(self)
        meta_layout = QVBoxLayout(meta)
        meta_layout.setContentsMargins(0, 0, 0, 0)

        meta_layout.addWidget(QLabel("JSON Key:"))
        meta_layout.addWidget(self._json_key)

        meta_layout.addWidget(QLabel("CSV Column:"))
        meta_layout.addWidget(self._csv_column)

        meta_layout.addWidget(QLabel("CSV Delimiter:"))
        meta_layout.addWidget(self._csv_delimiter)

        # ---- Attach safely to dialog layout ----
        dlg_layout = self.layout()
        if dlg_layout is not None:
            dlg_layout.addWidget(meta)

        # ---- Wiring ----
        self.currentChanged.connect(self._on_path_changed)
        self._update_fields(None)

    # ------------------------------------------------------------------

    def _on_path_changed(self, path: str) -> None:
        self._update_fields(Path(path) if path else None)

    def _update_fields(self, path: Optional[Path]) -> None:
        self._json_key.setEnabled(False)
        self._csv_column.setEnabled(False)
        self._csv_delimiter.setEnabled(False)

        if not path:
            return

        suf = path.suffix.lower()

        if suf in {".json", ".jsonl"}:
            self._json_key.setEnabled(True)

        elif suf == ".csv":
            self._csv_column.setEnabled(True)
            self._csv_delimiter.setEnabled(True)

    # ------------------------------------------------------------------

    def get_request(self) -> Optional[OpenRequest]:
        if self.exec() != QFileDialog.Accepted:
            return None

        path = Path(self.selectedFiles()[0])

        return OpenRequest(
            path=path,
            json_key=self._json_key.text().strip() or None,
            csv_column=self._csv_column.text().strip() or None,
            csv_delimiter=self._csv_delimiter.text().strip() or None,
        )
