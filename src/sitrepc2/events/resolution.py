# src/sitrepc2/dom/resolution.py

from __future__ import annotations
from typing import Optional, Dict

from sitrepc2.gazetteer.typedefs import RegionEntry, GroupEntry
from sitrepc2.review.pd_nodes import PDLocation, PDEvent
from sitrepc2.spatial.direction_axis import (
    annotate_direction_axis_for_event,
    build_direction_axis,
)
from sitrepc2.spatial.clustering import cluster_locations
from sitrepc2.events.typedefs import Location
from sitrepc2.spatial.distance import haversine_km


# ===============================================================
# REGION CONTEXT NARROWING
# ===============================================================

def apply_region_context_to_event(loc: PDLocation, region: RegionEntry) -> None:
    """
    Remove candidates whose LocaleEntry.region != region.name.
    """
    new = []
    for cand in loc.candidates:
        if cand.locale.region and cand.locale.region == region.name:
            new.append(cand)
        else:
            cand.is_region_mismatch = True
    loc.candidates = new or loc.candidates  # keep originals if none survive


# ===============================================================
# GROUP CONTEXT NARROWING
# ===============================================================

def apply_group_context_to_event(loc: PDLocation, group: GroupEntry) -> None:
    """
    Remove candidates whose locale.ru_group != group.name.
    """
    new = []
    for cand in loc.candidates:
        if cand.locale.ru_group == group.name:
            new.append(cand)
        else:
            cand.is_group_mismatch = True
    loc.candidates = new or loc.candidates


# ===============================================================
# FRONTLINE DISTANCES
# ===============================================================

def compute_frontline_distances(event: PDEvent, frontline) -> None:
    if frontline is None:
        return

    for loc in event.children:
        if not isinstance(loc, PDLocation):
            continue

        for cand in loc.candidates:
            lat = cand.locale.lat
            lon = cand.locale.lon
            cand.distance_from_frontline_km = frontline.shortest_distance_km(lat, lon)


# ===============================================================
# DIRECTION AXIS APPLICATION
# ===============================================================

def apply_direction_context_to_event(
    event: PDEvent,
    anchors: Dict[str, Optional[object]],
    frontline
) -> None:
    """
    If we have a direction anchor and a frontline, compute direction axes.
    """
    dir_anchor = anchors.get("direction")
    if not dir_anchor or not frontline:
        return

    # Build direction axis for entire event
    annotate_direction_axis_for_event(
        event=event,
        frontline=frontline,
        direction_city=dir_anchor,
        label="direction"
    )


# ===============================================================
# CLUSTER RESOLUTION
# ===============================================================

def perform_candidate_clustering(event: PDEvent) -> None:
    """
    Runs beam-search clustering and assigns resolved_locale to each PDLocation.
    """
    # Convert PDLocation → temporary Location objects
    tmp_locations = []
    index_lookup = {}
    i = 0
    for loc in event.children:
        if isinstance(loc, PDLocation):
            L = Location(
                location_id=i,
                name=loc.span_text,
                candidates=loc.candidates,
            )
            tmp_locations.append(L)
            index_lookup[i] = loc
            i += 1

    if not tmp_locations:
        return

    cluster = cluster_locations(tmp_locations)
    if cluster is None:
        return

    # Assign chosen locale back into PDLocation
    for loc_id, cand in cluster.assignments.items():
        pd_loc = index_lookup[loc_id]
        pd_loc.final_locale = cand.locale
        pd_loc.final_confidence = cand.confidence

    # Store diagnostics for GUI
    event.cluster_diagnostics = cluster.diagnostics
