# src/sitrepc2/gazetteer/aliases.py
from __future__ import annotations

from typing import List, Set, Tuple

from sitrepc2.gazetteer.typedefs import (
    LocaleEntry, RegionEntry, GroupEntry, DirectionEntry
)
from sitrepc2.util.normalize import normalize_location_key


def gather_aliases(
    locales: List[LocaleEntry],
    regions: List[RegionEntry],
    groups: List[GroupEntry],
    directions: List[DirectionEntry],
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """
    Returns:
        (
            locale_aliases,
            region_aliases,
            group_aliases,
            direction_aliases
        )
    """

    def normset(items):
        s: Set[str] = set()
        for entry in items:
            for a in entry.aliases:
                s.add(normalize_location_key(a))
            s.add(normalize_location_key(entry.name))
        return sorted(s)

    return (
        normset(locales),
        normset(regions),
        normset(groups),
        normset(directions),
    )
