# src/dbeditc2/widgets/details/lexicon_phrase_builder_view.py
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QTextEdit,
    QPushButton,
)

from dbeditc2.enums import CollectionKind


class LexiconPhraseBuilderView(QWidget):
    """
    Phrase constructor view for lexicon entries.

    Allows users to compose event or context phrases
    under strict construction rules enforced elsewhere.
    """

    phraseChanged = Signal(str)
    saveRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        main_layout = QVBoxLayout(self)

        # --- Phrase type selection ---
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Phrase type:", self))

        self._event_radio = QRadioButton("Event", self)
        self._context_radio = QRadioButton("Context", self)
        self._event_radio.setChecked(True)

        type_layout.addWidget(self._event_radio)
        type_layout.addWidget(self._context_radio)
        type_layout.addStretch()

        main_layout.addLayout(type_layout)

        # --- Phrase text ---
        main_layout.addWidget(QLabel("Phrase text:", self))
        self._phrase_edit = QTextEdit(self)
        main_layout.addWidget(self._phrase_edit)

        self._phrase_edit.textChanged.connect(
            lambda: self.phraseChanged.emit(self._phrase_edit.toPlainText())
        )

        # --- Detected components ---
        self._detected_label = QLabel("", self)
        main_layout.addWidget(self._detected_label)

        # --- Status ---
        self._status_label = QLabel("", self)
        main_layout.addWidget(self._status_label)

        # --- Actions ---
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self._save_btn = QPushButton("Save", self)
        self._cancel_btn = QPushButton("Cancel", self)

        self._save_btn.clicked.connect(self.saveRequested)
        self._cancel_btn.clicked.connect(self.cancelRequested)

        action_layout.addWidget(self._save_btn)
        action_layout.addWidget(self._cancel_btn)

        main_layout.addLayout(action_layout)

    def set_phrase_type(self, kind: CollectionKind) -> None:
        """
        Set the phrase type (event or context).
        """
        self._event_radio.setChecked(kind == CollectionKind.EVENT_PHRASES)
        self._context_radio.setChecked(kind == CollectionKind.CONTEXT_PHRASES)

    def set_phrase_text(self, text: str) -> None:
        """
        Set the phrase text.
        """
        self._phrase_edit.blockSignals(True)
        self._phrase_edit.setPlainText(text)
        self._phrase_edit.blockSignals(False)

    def set_validation_status(
        self,
        *,
        valid: bool,
        messages: list[str],
        detected_verbs: list[str],
        detected_keywords: list[str],
    ) -> None:
        """
        Update validation feedback and save button state.
        """
        self._save_btn.setEnabled(valid)

        parts = []
        if detected_keywords:
            parts.append(f"Holmes keywords: {', '.join(detected_keywords)}")
        if detected_verbs:
            parts.append(f"Verbs: {', '.join(detected_verbs)}")

        self._detected_label.setText(" | ".join(parts))

        if messages:
            self._status_label.setText(" • ".join(messages))
        else:
            self._status_label.setText("")

    def clear(self) -> None:
        """
        Reset the constructor.
        """
        self._phrase_edit.clear()
        self._detected_label.clear()
        self._status_label.clear()
        self._save_btn.setEnabled(False)
