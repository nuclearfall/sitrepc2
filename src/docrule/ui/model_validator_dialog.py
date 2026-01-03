from __future__ import annotations

from typing import List, Optional, Tuple

import spacy
from spacy.util import get_installed_models

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QMessageBox,
)


_SIZE_ORDER = {
    "trf": 4,
    "lg": 3,
    "md": 2,
    "sm": 1,
}


def _model_size_rank(name: str) -> int:
    for suffix, rank in _SIZE_ORDER.items():
        if name.endswith(f"_{suffix}"):
            return rank
    return 0


def _supports_coreferee(model_name: str) -> bool:
    try:
        nlp = spacy.load(model_name, disable=["ner", "parser", "tagger"])
        nlp.add_pipe("coreferee")
        return True
    except Exception:
        return False


class ModelValidatorDialog(QDialog):
    """
    Modal dialog validating available spaCy and coreferee models.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Validate NLP Models")
        self.setModal(True)
        self.resize(520, 400)

        self._selected_model: Optional[str] = None
        self._coreferee_enabled: bool = False

        self._build_ui()
        self._populate_models()
        self._apply_default_selection()
        self._update_ok_state()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Select at least one spaCy model.\n"
            "The largest available model is selected by default."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.model_list = QListWidget(self)
        self.model_list.itemChanged.connect(self._update_ok_state)
        self.model_list.currentItemChanged.connect(self._update_metadata)
        layout.addWidget(self.model_list, stretch=1)

        self.meta_label = QLabel("", self)
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

        button_row = QHBoxLayout()
        button_row.addStretch()

        self.ok_btn = QPushButton("OK", self)
        self.ok_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.clicked.connect(self.reject)

        button_row.addWidget(cancel_btn)
        button_row.addWidget(self.ok_btn)

        layout.addLayout(button_row)

    # ------------------------------------------------------------------

    def _populate_models(self) -> None:
        models = sorted(
            get_installed_models(),
            key=_model_size_rank,
            reverse=True,
        )

        if not models:
            QMessageBox.critical(
                self,
                "No Models Found",
                "No spaCy models are installed.\n\n"
                "Install one using:\n"
                "  python -m spacy download en_core_web_lg",
            )
            self.reject()
            return

        for name in models:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.model_list.addItem(item)

    # ------------------------------------------------------------------

    def _apply_default_selection(self) -> None:
        if self.model_list.count() == 0:
            return

        largest_item = self.model_list.item(0)
        largest_item.setCheckState(Qt.Checked)
        self.model_list.setCurrentItem(largest_item)

    # ------------------------------------------------------------------

    def _update_metadata(self) -> None:
        item = self.model_list.currentItem()
        if not item:
            self.meta_label.setText("")
            return

        name = item.text()
        supports_coref = _supports_coreferee(name)

        text = (
            f"<b>Model:</b> {name}<br>"
            f"<b>Coreferee:</b> "
            f"{'Supported' if supports_coref else 'Not supported'}"
        )

        self.meta_label.setText(text)

    # ------------------------------------------------------------------

    def _update_ok_state(self) -> None:
        checked = self._checked_models()
        self.ok_btn.setEnabled(bool(checked))

    # ------------------------------------------------------------------

    def _checked_models(self) -> List[str]:
        result: List[str] = []
        for i in range(self.model_list.count()):
            item = self.model_list.item(i)
            if item.checkState() == Qt.Checked:
                result.append(item.text())
        return result

    # ------------------------------------------------------------------

    def selected_configuration(self) -> Tuple[str, bool]:
        """
        Returns:
            (primary_spacy_model, coreferee_enabled)
        """
        checked = self._checked_models()
        if not checked:
            raise RuntimeError("No model selected")

        primary = sorted(checked, key=_model_size_rank, reverse=True)[0]
        coref = _supports_coreferee(primary)

        return primary, coref
