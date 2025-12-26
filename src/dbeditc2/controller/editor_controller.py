# src/dbeditc2/controller/editor_controller.py
from __future__ import annotations

from dbeditc2.enums import CollectionKind, EditorMode
from dbeditc2.services.gazetteer_read import (
    list_entities,
    load_entity,
)
from dbeditc2.services.gazetteer_search import search_entities
from dbeditc2.widgets.entry_details_stack import EntryDetailsStack
from dbeditc2.widgets.entry_list_view import EntryListView
from dbeditc2.widgets.navigation_tree import NavigationTree
from dbeditc2.widgets.search_panel import SearchPanel
from dbeditc2.widgets.app_toolbar import AppToolBar

from sitrepc2.gazetteer.alias_service import apply_alias_changes
from dbeditc2.services.gazetteer_search import _DOMAIN_FOR_COLLECTION


class EditorController:
    """
    Controller for Gazetteer browsing with alias editing support.

    Responsibilities:
    - Load entity lists
    - Load entity details
    - Track alias edit deltas
    - Apply alias changes via sitrepc2 services

    Scope:
    - Gazetteer only
    - Alias editing only
    """

    def __init__(
        self,
        *,
        navigation: NavigationTree,
        search: SearchPanel,
        entry_list: EntryListView,
        details: EntryDetailsStack,
        toolbar: AppToolBar,
    ) -> None:
        self._navigation = navigation
        self._search = search
        self._entry_list = entry_list
        self._details = details
        self._toolbar = toolbar

        self._current_collection: CollectionKind | None = None
        self._current_entity_id: int | None = None

        # Alias edit state
        self._original_aliases: set[str] = set()
        self._added_aliases: set[str] = set()
        self._removed_aliases: set[str] = set()

        # --- Wire signals ---
        self._navigation.collectionSelected.connect(self.on_collection_selected)
        self._entry_list.entrySelected.connect(self.on_entry_selected)
        self._search.searchTextChanged.connect(self.on_search_text_changed)
        self._search.searchSubmitted.connect(self.on_search_submitted)

        self._details.gazetteer_view.aliasAddRequested.connect(
            self.on_alias_added
        )
        self._details.gazetteer_view.aliasRemoveRequested.connect(
            self.on_alias_removed
        )

        self._toolbar.saveRequested.connect(self.on_save_aliases)
        self._toolbar.cancelRequested.connect(self.on_cancel_aliases)

        # Start in view mode
        self._toolbar.set_mode(EditorMode.VIEW)
        self._toolbar.set_actions_enabled(
            add=False,
            edit=False,
            remove=False,
            restore=False,
        )

    # ------------------------------------------------------------------
    # Collection / entity loading
    # ------------------------------------------------------------------

    def on_collection_selected(self, kind: CollectionKind) -> None:
        self._current_collection = kind
        self._current_entity_id = None

        entries = list_entities(kind)
        self._entry_list.set_entries(entries)
        self._details.show_empty()

    def on_entry_selected(self, entry_id: int) -> None:
        if self._current_collection is None:
            return

        entity = load_entity(self._current_collection, entry_id)

        self._details.show_gazetteer_view()
        self._details.gazetteer_view.set_entity_type(self._current_collection)
        self._details.gazetteer_view.set_entity_data(entity)

        # Initialize alias edit state
        self._current_entity_id = entry_id
        self._original_aliases = set(entity.aliases or [])
        self._added_aliases.clear()
        self._removed_aliases.clear()

        # Alias editing is the only enabled action for now
        self._toolbar.set_actions_enabled(
            add=False,
            edit=False,
            remove=False,
            restore=False,
        )

    # ------------------------------------------------------------------
    # Search handling
    # ------------------------------------------------------------------

    def on_search_text_changed(self, text: str) -> None:
        if self._current_collection is None:
            return

        if not text.strip():
            entries = list_entities(self._current_collection)
        else:
            entries = search_entities(
                collection=self._current_collection,
                text=text,
            )

        self._entry_list.set_entries(entries)
        self._details.show_empty()

    def on_search_submitted(self, text: str) -> None:
        self.on_search_text_changed(text)

    # ------------------------------------------------------------------
    # Alias editing
    # ------------------------------------------------------------------

    def on_alias_added(self, alias: str) -> None:
        alias = alias.strip()
        if not alias:
            return

        if alias in self._original_aliases:
            return

        self._added_aliases.add(alias)
        self._removed_aliases.discard(alias)
        self._refresh_alias_view()

    def on_alias_removed(self, alias: str) -> None:
        if alias in self._added_aliases:
            self._added_aliases.remove(alias)
        else:
            self._removed_aliases.add(alias)

        self._refresh_alias_view()

    def _refresh_alias_view(self) -> None:
        aliases = (
            self._original_aliases
            | self._added_aliases
        ) - self._removed_aliases

        view = self._details.gazetteer_view
        view._aliases_list.clear()
        view._aliases_list.addItems(sorted(aliases))

    # ------------------------------------------------------------------
    # Save / cancel
    # ------------------------------------------------------------------

    def on_save_aliases(self) -> None:
        if (
            self._current_entity_id is None
            or self._current_collection is None
        ):
            return

        if not self._added_aliases and not self._removed_aliases:
            return

        domain = _DOMAIN_FOR_COLLECTION[self._current_collection]

        apply_alias_changes(
            domain=domain,
            entity_ids=[self._current_entity_id],
            added=self._added_aliases,
            removed=self._removed_aliases,
        )

        # Reload entity to reflect canonical state
        self.on_entry_selected(self._current_entity_id)

    def on_cancel_aliases(self) -> None:
        if self._current_entity_id is None:
            return

        self.on_entry_selected(self._current_entity_id)
