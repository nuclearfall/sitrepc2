# src/sitrepc2/events/context/group.py

from __future__ import annotations
from typing import Dict, List, Optional

from shapely.geometry import Point, shape

from sitrepc2.events.typedefs import Location, LocaleCandidate, SitRepContext, CtxKind
from sitrepc2.gazetteer.typedefs import GroupEntry
from sitrepc2.events.context.base import normalize, matches_alias


BUFFER_DISTANCE_M = 10_000  # >10 km outside AO → discard
BOOST_IN_POLYGON = 0.40
BOOST_IN_BUFFER = 0.10
BOOST_RU_GROUP_MATCH = 0.50


def apply_group_constraints(
    location: Location,
    group_ctx: SitRepContext,
    group_lookup: Dict[str, GroupEntry],
    group_polygons: Dict[str, object],   # group_name.lower() → shapely polygon
) -> None:
    """
    Apply full operational-group filtering and scoring:

        1. Region hard filter (except neighbor fallback)
        2. AO polygon hit-test
        3. Distance >10 km → discard
        4. Inside → +0.40, buffer → +0.10
        5. locale.ru_group == group.name → +0.50
    """
    if group_ctx.kind != CtxKind.GROUP:
        return

    group_entry = resolve_group_entry(group_ctx.text, group_lookup)
    if group_entry is None:
        return

    group_name_norm = normalize(group_entry.name)

    if group_name_norm not in group_polygons:
        return

    group_polygon = group_polygons[group_name_norm]
    group_regions = {normalize(r) for r in group_entry.regions}
    group_neighbors = {normalize(n) for n in group_entry.neighbors}

    filtered: List[LocaleCandidate] = []

    for cand in location.candidates:
        loc_region = normalize(cand.locale.region)
        loc_ru_group = normalize(cand.locale.ru_group)

        # ---------------------------
        # 1. Region membership check
        # ---------------------------
        if loc_region not in group_regions:
            # Only allow if region belongs to neighboring group
            if not region_is_in_neighbor_group(loc_region, group_neighbors, group_lookup):
                continue

        # ---------------------------
        # 2. Geometry check
        # ---------------------------
        pt = Point(cand.locale.lon, cand.locale.lat)
        dist_m = group_polygon.distance(pt)

        if dist_m > BUFFER_DISTANCE_M:
            continue  # hard discard >10 km

        if group_polygon.contains(pt):
            cand.scores["group_polygon"] = BOOST_IN_POLYGON
        else:
            cand.scores["group_polygon"] = BOOST_IN_BUFFER

        # ---------------------------
        # 3. LocaleEntry.ru_group alignment
        # ---------------------------
        cand.scores["group_ru_group_match"] = (
            BOOST_RU_GROUP_MATCH if loc_ru_group == group_name_norm else 0.0
        )

        filtered.append(cand)

    location.candidates = filtered


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def resolve_group_entry(
    text: str,
    group_lookup: Dict[str, GroupEntry],
) -> Optional[GroupEntry]:
    """
    Resolve context text ("Tsentr Group") to a GroupEntry.
    """
    key = normalize(text)

    for name, entry in group_lookup.items():
        if matches_alias(key, entry.name, entry.aliases):
            return entry

    return None


def region_is_in_neighbor_group(
    region: str,
    neighbor_groups: set,
    group_lookup: Dict[str, GroupEntry],
) -> bool:
    """
    Returns True if a region belongs to ANY neighboring group.
    """
    for group_name in neighbor_groups:
        entry = group_lookup.get(group_name)
        if entry is None:
            continue
        if region in {normalize(r) for r in entry.regions}:
            return True
    return False
