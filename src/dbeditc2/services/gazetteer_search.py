# src/dbeditc2/services/gazetteer_search.py
from __future__ import annotations

from dbeditc2.enums import CollectionKind
from dbeditc2.models import EntrySummary

from sitrepc2.gazetteer.alias_service import search_entities_by_alias


# ---------------------------------------------------------------------
# Domain mapping
# ---------------------------------------------------------------------

_DOMAIN_FOR_COLLECTION: dict[CollectionKind, str] = {
    CollectionKind.LOCATIONS: "LOCATION",
    CollectionKind.REGIONS: "REGION",
    CollectionKind.GROUPS: "GROUP",
    CollectionKind.DIRECTIONS: "DIRECTION",
}


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def search_entities(
    *,
    collection: CollectionKind,
    text: str,
) -> list[EntrySummary]:
    """
    Search gazetteer entities by alias prefix.

    Read-only wrapper around sitrepc2 alias_service.
    """
    domain = _DOMAIN_FOR_COLLECTION.get(collection)
    if domain is None:
        return []

    results = search_entities_by_alias(
        domain=domain,
        search_text=text,
    )

    return [
        EntrySummary(
            entry_id=row["entity_id"],
            display_name=row["canonical_name"],
            editable=False,
        )
        for row in results
    ]
