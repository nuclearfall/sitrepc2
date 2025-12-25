from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QTextCursor,
    QTextCharFormat,
    QColor,
    QMouseEvent,
    QTextDocument,
)
from PySide6.QtWidgets import QTextEdit

from spacy.tokens import Doc, Token, Span


class DocumentViewer(QTextEdit):
    """
    Read-only interactive viewer for a spaCy Doc.
    """

    tokenSelected = Signal(object, object)  # Token, Optional[Span]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setReadOnly(True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        self._doc: Optional[Doc] = None
        self._spans: List[Span] = []

        self._hover_selections: List[QTextEdit.ExtraSelection] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_doc(
        self,
        doc: Doc,
        *,
        ruler_colors: Dict[str, str],
    ) -> None:
        self.clear()
        self._doc = doc
        self._spans.clear()
        self._hover_selections.clear()
        self.setExtraSelections([])

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.Start)

        for token in doc:
            cursor.insertText(token.text_with_ws)

        self._collect_spans()
        self._apply_highlighting(ruler_colors)

        cursor.movePosition(QTextCursor.Start)
        self.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Span collection & highlighting
    # ------------------------------------------------------------------

    def _collect_spans(self) -> None:
        if not self._doc:
            return
        self._spans.extend(self._doc.ents)

    def _apply_highlighting(self, ruler_colors: Dict[str, str]) -> None:
        cursor = self.textCursor()

        for span in self._spans:
            fmt = QTextCharFormat()

            if span.label_ in ruler_colors:
                fmt.setBackground(QColor(ruler_colors[span.label_]))
            else:
                fmt.setUnderlineStyle(QTextCharFormat.DotLine)
                fmt.setUnderlineColor(QColor("#888888"))

            cursor.setPosition(span.start_char)
            cursor.setPosition(span.end_char, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(fmt)

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        cursor = self.cursorForPosition(event.position().toPoint())
        self._update_hover(cursor.position())
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        cursor = self.cursorForPosition(event.position().toPoint())
        token = self._token_at_pos(cursor.position())
        span = self._span_for_token(token) if token else None

        if token:
            self.tokenSelected.emit(token, span)

        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    # Hoverhover handling (non-destructive)
    # ------------------------------------------------------------------

    def _update_hover(self, pos: int) -> None:
        self._hover_selections.clear()

        token = self._token_at_pos(pos)
        if not token:
            self.setExtraSelections([])
            return

        span = self._span_for_token(token)
        start = span.start_char if span else token.idx
        end = span.end_char if span else token.idx + len(token)

        sel = QTextEdit.ExtraSelection()
        sel.cursor = self.textCursor()
        sel.cursor.setPosition(start)
        sel.cursor.setPosition(end, QTextCursor.KeepAnchor)

        fmt = QTextCharFormat()
        fmt.setOutline(True)
        fmt.setOutlinePen(Qt.DotLine)
        sel.format = fmt

        self._hover_selections.append(sel)
        self.setExtraSelections(self._hover_selections)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _token_at_pos(self, pos: int) -> Optional[Token]:
        if not self._doc:
            return None

        for token in self._doc:
            if token.idx <= pos < token.idx + len(token):
                return token
        return None

    def _span_for_token(self, token: Token) -> Optional[Span]:
        for span in self._spans:
            if span.start <= token.i < span.end:
                return span
        return None

    # ------------------------------------------------------------------
    # Clipboard & drag-drop interception
    # ------------------------------------------------------------------

    def insertFromMimeData(self, source) -> None:
        text = source.text()
        if text:
            self.parent().load_text_from_external(text)

    def dropEvent(self, event) -> None:
        mime = event.mimeData()

        if mime.hasUrls():
            for url in mime.urls():
                self.parent().load_file_from_external(url.toLocalFile())
        elif mime.hasText():
            self.parent().load_text_from_external(mime.text())
