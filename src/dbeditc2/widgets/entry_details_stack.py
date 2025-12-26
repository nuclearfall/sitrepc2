# src/dbeditc2/widgets/entry_details_stack.py
from __future__ import annotations

from PySide6.QtWidgets import QStackedWidget

from dbeditc2.widgets.details.empty_state_view import EmptyStateView
from dbeditc2.widgets.details.gazetteer_details_view import GazetteerDetailsView
from dbeditc2.widgets.details.lexicon_phrase_builder_view import (
    LexiconPhraseBuilderView,
)


class EntryDetailsStack(QStackedWidget):
    """
    Container for switching between details views.

    This widget owns all detail panels and exposes
    explicit methods for selecting which one is shown.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._empty_view = EmptyStateView(self)
        self._gazetteer_view = GazetteerDetailsView(self)
        self._lexicon_builder_view = LexiconPhraseBuilderView(self)

        self.addWidget(self._empty_view)
        self.addWidget(self._gazetteer_view)
        self.addWidget(self._lexicon_builder_view)

        self.show_empty()

    def show_empty(self) -> None:
        self.setCurrentWidget(self._empty_view)

    def show_gazetteer_view(self) -> None:
        self.setCurrentWidget(self._gazetteer_view)

    def show_lexicon_builder(self) -> None:
        self.setCurrentWidget(self._lexicon_builder_view)

    def set_read_only(self, read_only: bool) -> None:
        """
        Propagate read-only state to the active view.
        """
        widget = self.currentWidget()
        if hasattr(widget, "set_read_only"):
            widget.set_read_only(read_only)

    @property
    def gazetteer_view(self) -> GazetteerDetailsView:
        return self._gazetteer_view

    @property
    def lexicon_builder_view(self) -> LexiconPhraseBuilderView:
        return self._lexicon_builder_view
