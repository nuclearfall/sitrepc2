# src/sitrepc2/events/context/region.py

from __future__ import annotations
from typing import Dict, List

from sitrepc2.events.typedefs import Location, LocaleCandidate, SitRepContext, CtxKind
from sitrepc2.gazetteer.typedefs import RegionEntry
from sitrepc2.events.context.base import normalize, matches_alias


def apply_region_constraints(
    location: Location,
    region_ctx: SitRepContext,
    region_lookup: Dict[str, RegionEntry],
) -> None:
    """
    Apply DOM-level region filtering:

        • Region match → keep (strong)
        • Neighbor region → keep (soft)
        • All others → discard

    region_lookup maps canonical lowercase region name → RegionEntry.
    """
    if region_ctx.kind != CtxKind.REGION:
        return

    region_entry = resolve_region_entry(region_ctx.text, region_lookup)
    if region_entry is None:
        return

    canonical_region = normalize(region_entry.name)
    neighbors = {normalize(n) for n in region_entry.neighbors}

    filtered: List[LocaleCandidate] = []

    for cand in location.candidates:
        loc_region = normalize(cand.locale.region)

        if loc_region == canonical_region:
            cand.scores["region_match"] = 1.0
            filtered.append(cand)
            continue

        if loc_region in neighbors:
            cand.scores["region_neighbor"] = 0.25
            filtered.append(cand)
            continue

    location.candidates = filtered


def resolve_region_entry(
    text: str,
    region_lookup: Dict[str, RegionEntry],
) -> RegionEntry | None:
    """
    Resolve a text form (from context) to a RegionEntry using:
        • canonical name
        • alias list
    """
    key = normalize(text)

    for region_name, entry in region_lookup.items():
        if matches_alias(key, entry.name, entry.aliases):
            return entry

    return None
