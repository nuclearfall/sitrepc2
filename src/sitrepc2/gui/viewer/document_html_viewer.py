from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Signal, QUrl, QObject, Slot
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

from spacy.tokens import Doc, Span


# ---------------------------------------------------------------------
# JS bridge
# ---------------------------------------------------------------------

class _JsBridge(QObject):
    tokenClicked = Signal(int, object)  # token_i, span_id or None

    @Slot(int, str)
    def onTokenClicked(self, token_i: int, span_id: str) -> None:
        self.tokenClicked.emit(token_i, span_id or None)


# ---------------------------------------------------------------------
# Viewer
# ---------------------------------------------------------------------

class DocumentHtmlViewer(QWebEngineView):
    """
    HTML-based interactive viewer for spaCy Docs.

    Guarantees:
    - Token-precise DOM nodes
    - Unified entity span highlighting
    - Unified tooltip per entity (hover anywhere)
    - Whitespace inside spans is highlighted
    """

    tokenSelected = Signal(object, object)  # Token, Optional[Span]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._doc: Optional[Doc] = None
        self._span_map: Dict[str, Span] = {}

        self._bridge = _JsBridge()
        self._bridge.tokenClicked.connect(self._on_token_clicked)

        channel = QWebChannel(self.page())
        channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(channel)

    # ------------------------------------------------------------------

    def set_doc(self, doc: Doc, *, ruler_colors: Dict[str, str]) -> None:
        self._doc = doc
        self._span_map.clear()
        self.setHtml(self._build_html(doc, ruler_colors), QUrl("qrc:///"))

    # ------------------------------------------------------------------

    def _on_token_clicked(self, token_i: int, span_id: Optional[str]) -> None:
        if not self._doc:
            return
        token = self._doc[token_i]
        span = self._span_map.get(span_id) if span_id else None
        self.tokenSelected.emit(token, span)

    # ------------------------------------------------------------------

    def _build_html(self, doc: Doc, ruler_colors: Dict[str, str]) -> str:
        spans_by_token: Dict[int, str] = {}
        span_labels: Dict[int, str] = {}
        span_first: Dict[int, bool] = {}
        span_last: Dict[int, bool] = {}

        # ----------------------------------------
        # Build span metadata
        # ----------------------------------------

        for idx, span in enumerate(doc.ents):
            span_id = f"span_{idx}"
            self._span_map[span_id] = span

            first_i = span[0].i
            last_i = span[-1].i

            for tok in span:
                spans_by_token[tok.i] = span_id
                span_labels[tok.i] = span.label_
                if tok.i == first_i:
                    span_first[tok.i] = True
                if tok.i == last_i:
                    span_last[tok.i] = True

        css = self._build_css(ruler_colors)
        body_parts: list[str] = []

        # ----------------------------------------
        # Emit token HTML
        # ----------------------------------------

        for tok in doc:
            span_id = spans_by_token.get(tok.i, "")
            entity_label = span_labels.get(tok.i, "")

            attrs = [
                'class="token"',
                f'data-token-i="{tok.i}"',
                f'data-span-id="{span_id}"',
            ]

            if entity_label:
                attrs.append(f'data-entity-label="{entity_label}"')
                if span_first.get(tok.i):
                    attrs.append('data-span-first="1"')
                if span_last.get(tok.i):
                    attrs.append('data-span-last="1"')

                # absorb whitespace inside entity span
                text = tok.text + tok.whitespace_
                trailing = ""
            else:
                text = tok.text
                trailing = tok.whitespace_

            body_parts.append(
                f"<span {' '.join(attrs)}>{text}</span>{trailing}"
            )

        return (
            "<!DOCTYPE html>"
            "<html>"
            "<head>"
            '<meta charset="utf-8">'
            "<style>"
            f"{css}"
            "</style>"
            '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
            "<script>"
            "new QWebChannel(qt.webChannelTransport, function(channel) {"
            "  window.bridge = channel.objects.bridge;"
            "});"

            # ------------------------------
            # Unified hover logic
            # ------------------------------
            "function setSpanHover(spanId, on) {"
            "  if (!spanId) return;"
            "  const first = document.querySelector("
            "    '.token[data-span-id=\"' + spanId + '\"][data-span-first]'"
            "  );"
            "  if (!first) return;"
            "  if (on) first.classList.add('span-hover');"
            "  else first.classList.remove('span-hover');"
            "}"

            "document.addEventListener('mouseover', function(e) {"
            "  const el = e.target.closest('.token[data-span-id]');"
            "  if (!el) return;"
            "  setSpanHover(el.dataset.spanId, true);"
            "});"

            "document.addEventListener('mouseout', function(e) {"
            "  const el = e.target.closest('.token[data-span-id]');"
            "  if (!el) return;"
            "  setSpanHover(el.dataset.spanId, false);"
            "});"

            "document.addEventListener('click', function(e) {"
            "  const el = e.target.closest('.token');"
            "  if (!el) return;"
            "  bridge.onTokenClicked("
            "    parseInt(el.dataset.tokenI),"
            "    el.dataset.spanId || ''"
            "  );"
            "});"
            "</script>"
            "</head>"
            "<body>"
            f"{''.join(body_parts)}"
            "</body>"
            "</html>"
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _build_css(ruler_colors: Dict[str, str]) -> str:
        rules = [
            "body { white-space: pre-wrap; }",
            ".token { position: relative; cursor: pointer; }",

            # --- Unified span highlight ---
            (
                ".token[data-entity-label] {"
                "  padding: 0.12em 0.18em;"
                "  box-decoration-break: clone;"
                "  -webkit-box-decoration-break: clone;"
                "}"
            ),

            # --- Collapse seams between tokens ---
            (
                ".token[data-entity-label]:not([data-span-first]) {"
                "  margin-left: -0.18em;"
                "}"
            ),

            # --- Rounded edges ---
            (
                ".token[data-span-first] {"
                "  border-top-left-radius: 0.45em;"
                "  border-bottom-left-radius: 0.45em;"
                "}"
            ),
            (
                ".token[data-span-last] {"
                "  border-top-right-radius: 0.45em;"
                "  border-bottom-right-radius: 0.45em;"
                "}"
            ),

            # --- Unified tooltip (driven by JS) ---
            (
                ".token[data-span-first].span-hover::after {"
                "  content: attr(data-entity-label);"
                "  position: absolute;"
                "  top: -1.6em;"
                "  left: 0;"
                "  background: rgba(40,40,40,0.95);"
                "  color: #fff;"
                "  font-size: 0.75em;"
                "  padding: 2px 6px;"
                "  border-radius: 4px;"
                "  white-space: nowrap;"
                "  pointer-events: none;"
                "  z-index: 1000;"
                "}"
            ),
        ]

        for label, color in ruler_colors.items():
            rules.append(
                f'.token[data-entity-label="{label}"] {{ '
                f'background-color: {color}; '
                f'}}'
            )

        return "\n".join(rules)
