from __future__ import annotations

from dbeditc2.enums import CollectionKind, EditorMode
from dbeditc2.services.gazetteer_read import load_entity
from dbeditc2.services.gazetteer_alias_browser import list_aliases
from dbeditc2.services.gazetteer_search import _DOMAIN_FOR_COLLECTION

from dbeditc2.widgets.entry_details_stack import EntryDetailsStack
from dbeditc2.widgets.entry_list_view import EntryListView
from dbeditc2.widgets.navigation_tree import NavigationTree
from dbeditc2.widgets.search_panel import SearchPanel
from dbeditc2.widgets.app_toolbar import AppToolBar

from sitrepc2.gazetteer.alias_service import apply_alias_changes


class EditorController:
    """
    Controller for Gazetteer browsing with alias editing support.

    Scope:
    - Gazetteer only
    - Alias editing only
    - No structural mutation
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

        self._original_aliases: set[str] = set()
        self._added_aliases: set[str] = set()
        self._removed_aliases: set[str] = set()

        # --------------------------------------------------
        # Signal wiring
        # --------------------------------------------------

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

        # Toolbar intent mapping (authoritative)
        self._toolbar.editRequested.connect(self.on_save_aliases)
        self._toolbar.restoreRequested.connect(self.on_cancel_aliases)

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

        entries = list_aliases(kind=kind)
        self._entry_list.set_entries(entries)
        self._details.show_empty()

    def on_entry_selected(self, entry_id: int) -> None:
        if self._current_collection is None:
            return

        entity = load_entity(self._current_collection, entry_id)

        self._details.show_gazetteer_view()
        self._details.gazetteer_view.set_entity_type(self._current_collection)
        self._details.gazetteer_view.set_entity_data(entity)

        self._current_entity_id = entry_id
        self._original_aliases = set(entity.aliases or [])
        self._added_aliases.clear()
        self._removed_aliases.clear()

        # Enable commit / discard
        self._toolbar.set_actions_enabled(
            add=False,
            edit=True,
            remove=False,
            restore=True,
        )

    # ------------------------------------------------------------------
    # Search handling
    # ------------------------------------------------------------------

    def on_search_text_changed(self, text: str) -> None:
        if self._current_collection is None:
            raise RuntimeError("Search invoked without active collection")

        entries = list_aliases(
            kind=self._current_collection,
            search_text=text,
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
        if not alias or alias in self._original_aliases:
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
            self._original_aliases | self._added_aliases
        ) - self._removed_aliases

        view = self._details.gazetteer_view
        view._aliases_list.clear()
        view._aliases_list.addItems(sorted(aliases))

    # ------------------------------------------------------------------
    # Commit / discard
    # ------------------------------------------------------------------

    def on_save_aliases(self) -> None:
        if (
            self._current_entity_id is None
            or self._current_collection is None
            or not (self._added_aliases or self._removed_aliases)
        ):
            return

        domain = _DOMAIN_FOR_COLLECTION[self._current_collection]

        apply_alias_changes(
            domain=domain,
            entity_ids=[self._current_entity_id],
            added=self._added_aliases,
            removed=self._removed_aliases,
        )

        self.on_entry_selected(self._current_entity_id)

    def on_cancel_aliases(self) -> None:
        if self._current_entity_id is None:
            return

        self.on_entry_selected(self._current_entity_id)
