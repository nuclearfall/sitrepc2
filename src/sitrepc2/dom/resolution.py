# src/sitrepc2/dom/resolution.py

from __future__ import annotations
from typing import Optional, Dict

from sitrepc2.gazetteer.typedefs import RegionEntry, GroupEntry
from sitrepc2.review.pd_nodes import PDLocation, PDEvent
from sitrepc2.spatial.direction_axis import (
    annotate_direction_axis_for_event,
)
from sitrepc2.spatial.clustering import cluster_locations
from sitrepc2.dom.typedefs import Location
from sitrepc2.spatial.distance import haversine_km


# ===============================================================
# REGION CONTEXT NARROWING
# ===============================================================

def apply_region_context_to_event(loc: PDLocation, region: RegionEntry) -> None:
    """
    Remove candidates that do not match the region constraint.
    RegionEntry.name is canonical (e.g. "Kherson Oblast").

    PDLocation.candidates is replaced with filtered candidates if any survive.
    If nothing matches, original list is retained (fail-safe).
    """
    surviving = []
    for cand in loc.candidates:
        locale_region = cand.locale.region
        if locale_region and locale_region == region.name:
            surviving.append(cand)
        else:
            cand.is_region_mismatch = True

    # Fail-safe: never destroy all candidates unless explicitly allowed
    loc.candidates = surviving or loc.candidates


# ===============================================================
# GROUP CONTEXT NARROWING
# ===============================================================

def apply_group_context_to_event(loc: PDLocation, group: GroupEntry) -> None:
    """
    Remove candidates whose LocaleEntry.ru_group does not match group.name.

    LocaleEntry.ru_group is canonical (matches group.name exactly).
    """
    surviving = []
    for cand in loc.candidates:
        if cand.locale.ru_group == group.name:
            surviving.append(cand)
        else:
            cand.is_group_mismatch = True

    loc.candidates = surviving or loc.candidates


# ===============================================================
# FRONTLINE DISTANCES
# ===============================================================

def compute_frontline_distances(event: PDEvent, frontline) -> None:
    """
    Compute frontline distance (km) for every candidate.

    This function is idempotent and additive: it does not remove candidates,
    only annotates them with .distance_from_frontline_km.
    """
    if frontline is None:
        return

    for loc in event.children:
        if not isinstance(loc, PDLocation):
            continue

        for cand in loc.candidates:
            cand.distance_from_frontline_km = frontline.shortest_distance_km(
                cand.locale.lat,
                cand.locale.lon
            )


# ===============================================================
# DIRECTION AXIS APPLICATION
# ===============================================================

def apply_direction_context_to_event(
    event: PDEvent,
    anchors: Dict[str, Optional[object]],
    frontline
) -> None:
    """
    If a direction anchor (LocaleEntry) and a frontline exist:
    build a directional axis and annotate the event's PDLocations.

    anchors = {
        "direction": LocaleEntry | None,
        "proximity": LocaleEntry | None
    }

    Only the `"direction"` anchor is used for axis scoring.
    """

    dir_anchor = anchors.get("direction")
    if dir_anchor is None or frontline is None:
        return

    annotate_direction_axis_for_event(
        event=event,
        frontline=frontline,
        direction_city=dir_anchor,  # already a LocaleEntry
        label="direction"
    )


# ===============================================================
# CLUSTER RESOLUTION
# ===============================================================

def perform_candidate_clustering(event: PDEvent) -> None:
    """
    Performs spatial clustering across all PDLocations in an event
    and selects the optimal locale candidate for each location.

    Steps:
      1. Convert PDLocation → temporary Location objects
      2. Run cluster_locations() to score and assemble best-fit combinations
      3. Assign resolved entities back onto PDLocation.final_locale

    After completion:
      - PDLocation.final_locale: LocaleEntry
      - PDLocation.final_confidence: float
      - event.cluster_diagnostics: optional debug/GUI info
    """
    tmp_locations = []
    index_map = {}
    loc_id = 0

    # Build temporary Location objects
    for loc in event.children:
        if isinstance(loc, PDLocation):
            tmp = Location(
                location_id=loc_id,
                name=loc.span_text,
                candidates=loc.candidates,
            )
            tmp_locations.append(tmp)
            index_map[loc_id] = loc
            loc_id += 1

    if not tmp_locations:
        return

    cluster = cluster_locations(tmp_locations)
    if cluster is None:
        return

    # Assign resolved locale candidates back into PDLocation nodes
    for lid, cand in cluster.assignments.items():
        pd_loc = index_map[lid]
        pd_loc.final_locale = cand.locale
        pd_loc.final_confidence = cand.confidence

    event.cluster_diagnostics = cluster.diagnostics
