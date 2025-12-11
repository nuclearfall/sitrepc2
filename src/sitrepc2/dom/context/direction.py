# src/sitrepc2/events/context/direction.py

from __future__ import annotations
from typing import Dict, List, Optional

from sitrepc2.events.context.base import normalize, matches_alias
from sitrepc2.events.typedefs import Location, LocaleCandidate, SitRepContext, CtxKind
from sitrepc2.gazetteer.typedefs import DirectionEntry, LocaleEntry

from sitrepc2.spatial.direction_axis import (
    build_direction_axis,
    annotate_direction_axis_for_candidates,
)
from sitrepc2.spatial.frontline import Frontline
from sitrepc2.gazetteer.index import GazetteerIndex


# ------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------

def apply_direction_constraints(
    location: Location,
    direction_ctx: SitRepContext,
    gazetteer: GazetteerIndex,
    direction_lookup: Dict[str, DirectionEntry],
    frontline: Frontline,
) -> None:
    """
    Apply a directional context to a Location.

    Behavior:
        • Interpret direction context text to a DirectionEntry.
        • Resolve anchor LocaleEntries (DirectionEntry.anchors → CIDs).
        • Build direction axes from anchor cities to frontline.
        • Score candidates using projection:
              - dir_cross_km  (distance from axis)
              - dir_along_km  (position along axis)
        • Apply soft penalties for large cross-axis deviations.
        • Never fully discard candidates.
    """
    if direction_ctx.kind != CtxKind.DIRECTION:
        return

    direction_entry = resolve_direction_entry(direction_ctx.text, direction_lookup)
    if direction_entry is None:
        return

    # Resolve anchor cities
    anchors = resolve_anchor_entries(direction_entry, gazetteer)
    if not anchors:
        return

    # Apply annotation for each axis
    for anchor in anchors:
        _apply_axis_to_candidates(location, anchor, frontline, direction_entry.name)


# ------------------------------------------------------------
# INTERNAL HELPERS
# ------------------------------------------------------------

def resolve_direction_entry(
    text: str,
    lookup: Dict[str, DirectionEntry],
) -> Optional[DirectionEntry]:
    """
    Resolve raw text to a DirectionEntry using names and aliases.
    """
    key = normalize(text)

    for _, entry in lookup.items():
        if matches_alias(key, entry.name, entry.aliases):
            return entry

    return None


def resolve_anchor_entries(
    entry: DirectionEntry,
    gazetteer: GazetteerIndex,
) -> List[LocaleEntry]:
    """
    Convert DirectionEntry.anchors (cid list) into actual LocaleEntry objects.
    """
    anchors: List[LocaleEntry] = []
    for cid in entry.anchors:
        loc = gazetteer.get_locale_by_cid(cid)
        if loc is not None:
            anchors.append(loc)
    return anchors


def _apply_axis_to_candidates(
    location: Location,
    anchor: LocaleEntry,
    frontline: Frontline,
    direction_label: str,
) -> None:
    """
    Build a direction axis from one anchor → frontline,
    then annotate candidate scores.
    """
    try:
        axis = build_direction_axis(frontline, anchor)
    except Exception:
        return

    annotate_direction_axis_for_candidates(
        axis,
        location.candidates,
        label=direction_label,
    )

    # Apply soft penalties based on cross-axis deviation
    for cand in location.candidates:
        cross = cand.scores.get("dir_cross_km")
        along = cand.scores.get("dir_along_km")

        if cross is None:
            continue

        # Soft scoring: encourage closeness to axis
        # (values chosen empirically — easily tunable later)
        if cross < 5:
            bonus = 0.30
        elif cross < 10:
            bonus = 0.15
        elif cross < 20:
            bonus = 0.05
        else:
            bonus = -0.05  # mild penalty, still not a discard

        cand.scores[f"direction_axis_{direction_label}"] = bonus
