# src/sitrepc2/spatial/direction_axis.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Optional, Iterable

from sitrepc2.spatial.distance import haversine_km
from sitrepc2.dom.typedefs import LocaleCandidate
from sitrepc2.gazetteer.typedefs import LocaleEntry
from sitrepc2.review.pd_nodes import PDLocation, PDEvent


# ===============================================================
# MODEL
# ===============================================================

@dataclass(frozen=True)
class DirectionAxis:
    """
    A geometric axis defined by:
        - origin (lat, lon)      = direction city
        - vector (dlat, dlon)    = normalized direction toward the frontline
    """
    origin_lat: float
    origin_lon: float
    dlat: float
    dlon: float


# ===============================================================
# INTERNAL HELPERS
# ===============================================================

def _normalize_vector(dlat: float, dlon: float) -> tuple[float, float]:
    mag = (dlat**2 + dlon**2) ** 0.5
    if mag == 0:
        return (0.0, 0.0)
    return (dlat / mag, dlon / mag)


def _project_to_axis(axis: DirectionAxis, lat: float, lon: float) -> tuple[float, float]:
    """
    Compute (along_km, cross_km) for a point relative to the axis.
    Uses Haversine distances to approximate projection magnitudes.
    """
    origin = (axis.origin_lat, axis.origin_lon)

    # Small-displacement km distances along cardinal directions
    north_km = haversine_km(origin[0], origin[1], lat, origin[1])
    east_km  = haversine_km(origin[0], origin[1], origin[0], lon)

    # restore signs
    if lat < origin[0]:
        north_km = -north_km
    if lon < origin[1]:
        east_km = -east_km

    px, py = north_km, east_km
    vx, vy = axis.dlat, axis.dlon

    # dot product → projection length
    along = px * vx + py * vy

    # perpendicular distance
    proj_x = along * vx
    proj_y = along * vy
    cross = ((px - proj_x)**2 + (py - proj_y)**2)**0.5

    return along, cross


# ===============================================================
# PUBLIC API
# ===============================================================

def build_direction_axis(frontline, direction_city: LocaleEntry) -> DirectionAxis:
    """
    Build a direction axis starting at direction_city and pointing toward
    the nearest point on the frontline.
    """
    lat0 = direction_city.lat
    lon0 = direction_city.lon

    near_lat, near_lon = frontline.closest_point(lat0, lon0)
    dlat = near_lat - lat0
    dlon = near_lon - lon0
    ndlat, ndlon = _normalize_vector(dlat, dlon)

    return DirectionAxis(
        origin_lat=lat0,
        origin_lon=lon0,
        dlat=ndlat,
        dlon=ndlon,
    )


def annotate_direction_axis_for_candidates(
    axis: DirectionAxis,
    candidates: Sequence[LocaleCandidate],
    *,
    label: str | None = None,
) -> None:
    """
    Mutates each LocaleCandidate.scores with:
        dir_cross_km
        dir_along_km
    """
    for cand in candidates:
        lat = cand.locale.lat
        lon = cand.locale.lon

        along, cross = _project_to_axis(axis, lat, lon)
        cand.scores["dir_cross_km"] = cross
        cand.scores["dir_along_km"] = along
        if label:
            cand.scores["dir_label"] = label


def annotate_direction_axis_for_event(
    event: PDEvent,
    frontline,
    direction_city: LocaleEntry,
    *,
    label: str | None = None,
) -> Optional[DirectionAxis]:
    """
    Compute direction axis for an event and annotate all candidate locations.

    This version is aligned with the DOM PD tree design:
    - iterates over event.children
    - processes only PDLocation nodes
    - collects all candidates from all PDLocations
    """
    all_candidates = []

    # Gather candidates from each PDLocation under the event
    for child in event.children:
        if isinstance(child, PDLocation):
            all_candidates.extend(child.candidates)

    if not all_candidates:
        return None

    axis = build_direction_axis(frontline, direction_city)
    annotate_direction_axis_for_candidates(axis, all_candidates, label=label)
    return axis
