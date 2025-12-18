# src/sitrepc2/gazetteer/aliases.py
from __future__ import annotations

from typing import List, Set, Tuple, Iterable, Protocol

from sitrepc2.gazetteer.typedefs import (
    LocaleEntry,
    RegionEntry,
    GroupEntry,
    DirectionEntry,
)
from sitrepc2.gazetteer.io import load_gazetteer_from_db
from sitrepc2.util.normalize import normalize_location_key

class _HasNameAliases(Protocol):
    name: str
    aliases: List[str]


def _normset(entries: Iterable[_HasNameAliases]) -> List[str]:
    """
    Normalize and deduplicate all aliases + names from a sequence of entries.
    Returns a sorted list of unique normalized strings.
    """
    s: Set[str] = set()
    for entry in entries:
        # aliases
        for a in entry.aliases:
            s.add(normalize_location_key(a))
        # canonical name
        s.add(normalize_location_key(entry.name))
    return sorted(s)


def gather_aliases() -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Compute normalized alias/name sets for each gazetteer category.

    Args:
        locales, regions, groups, directions:
            In-memory dataclass lists (typically from DB).


    Returns:
        (
            locale_aliases,
            region_aliases,
            group_aliases,
            direction_aliases
        )

    Each returned list contains unique, normalized strings suitable for
    fast membership checks or feeding into entity rulers, patterns, etc.
    """
    locales, regions, groups, directions = load_gazetteer_from_db()

    return (
        _normset(locales),
        _normset(regions),
        _normset(groups),
        _normset(directions),
    )

def gather_aliases_from_db(
) -> Tuple[List[str], List[str], List[str], List[str]]:
    return gather_aliases()

def add_gazetteer_ruler(nlp: Language) -> Language:
    """
    Load the gazetteer from the authoritative records DB and install
    LOCALE / REGION / GROUP / DIRECTION entity rulers.

    This is the canonical DB-backed entry point.
    """
    locale_aliases, region_aliases, group_aliases, direction_aliases = (
        gather_aliases_from_db()
    )

    return _install_patterns_from_alias_lists(
        nlp,
        locale_aliases=locale_aliases,
        region_aliases=region_aliases,
        group_aliases=group_aliases,
        direction_aliases=direction_aliases,
    )

def add_entity_rulers_from_db(nlp: Language) -> Language:
    """
    Backward-compatible alias for add_gazetteer_ruler().
    """
    return add_gazetteer_ruler(nlp)
