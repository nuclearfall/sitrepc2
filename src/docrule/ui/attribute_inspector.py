from __future__ import annotations

from typing import Dict, Iterable, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QScrollArea,
)

from spacy.tokens import Token, Span


class AttributeInspector(QWidget):
    """
    Fixed, read-only attribute inspector.

    Displays attributes for:
    - A span if the selected token belongs to one
    - Otherwise the token itself

    Attributes are shown as Key | Value pairs.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._grid = QGridLayout()
        self._grid.setColumnStretch(1, 1)

        container = QWidget(self)
        container.setLayout(self._grid)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self._clear_grid()

    def set_token(self, token: Token) -> None:
        """
        Display attributes for a token.
        """
        attrs = self._token_attributes(token)
        self._populate(attrs)

    def set_span(self, span: Span) -> None:
        """
        Display attributes for a span.
        """
        attrs = self._span_attributes(span)
        self._populate(attrs)

    # ------------------------------------------------------------------
    # Attribute builders
    # ------------------------------------------------------------------

    def _token_attributes(self, token: Token) -> Dict[str, str]:
        attrs: Dict[str, str] = {
            "Text": token.text,
            "Lemma": token.lemma_,
            "POS": token.pos_,
            "Tag": token.tag_,
            "Dependency": token.dep_,
            "Index": str(token.i),
            "Entity Type": token.ent_type_ or "No entity type",
        }

        # Coreference info (inspection only)
        if hasattr(token.doc._, "coref_chains"):
            mentions = [
                str(chain)
                for chain in token.doc._.coref_chains
                if token in chain
            ]
            attrs["Coreference"] = (
                "; ".join(mentions) if mentions else "None"
            )

        return attrs

    def _span_attributes(self, span: Span) -> Dict[str, str]:
        attrs: Dict[str, str] = {
            "Text": span.text,
            "Label": span.label_ or "No entity type",
            "Start Token": str(span.start),
            "End Token": str(span.end),
            "Length": str(len(span)),
        }

        # Coreference info (inspection only)
        if hasattr(span.doc._, "coref_chains"):
            mentions = [
                str(chain)
                for chain in span.doc._.coref_chains
                if any(tok in chain for tok in span)
            ]
            attrs["Coreference"] = (
                "; ".join(mentions) if mentions else "None"
            )

        return attrs

    # ------------------------------------------------------------------
    # Grid helpers
    # ------------------------------------------------------------------

    def _populate(self, attrs: Dict[str, str]) -> None:
        self._clear_grid()

        for row, (key, value) in enumerate(attrs.items()):
            key_label = QLabel(key)
            key_label.setStyleSheet("font-weight: bold;")
            value_label = QLabel(value)
            value_label.setWordWrap(True)

            self._grid.addWidget(key_label, row, 0)
            self._grid.addWidget(value_label, row, 1)

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
