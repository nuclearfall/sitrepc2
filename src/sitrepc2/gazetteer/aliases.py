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


def gather_aliases(
    locales: List[LocaleEntry],
    regions: List[RegionEntry],
    groups: List[GroupEntry],
    directions: List[DirectionEntry],
) -> Tuple[List[str], List[str], List[str], List[str]]:
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
    return (
        _normset(locales),
        _normset(regions),
        _normset(groups),
        _normset(directions),
    )


def gather_aliases_from_db() -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Convenience helper: load gazetteer data from the SQLite database and
    return normalized alias/name sets for all four categories.

    Returns:
        (
            locale_aliases,
            region_aliases,
            group_aliases,
            direction_aliases
        )
    """
    regions, groups, locales, directions = load_gazetteer_from_db()
    return gather_aliases(locales, regions, groups, directions)
