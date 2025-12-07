# src/sitrepc2/spatial/direction_axis.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Optional

from sitrepc2.spatial.distance import haversine_km
from sitrepc2.events.typedefs import LocaleCandidate, Location, Event
from sitrepc2.gazetteer.typedefs import LocaleEntry


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


# ---------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------

def _normalize_vector(dlat: float, dlon: float) -> tuple[float, float]:
    mag = (dlat**2 + dlon**2) ** 0.5
    if mag == 0:
        return (0.0, 0.0)
    return (dlat / mag, dlon / mag)


def _project_to_axis(axis: DirectionAxis, lat: float, lon: float) -> tuple[float, float]:
    """
    Compute (along_km, cross_km) for a point relative to the axis.
    Uses haversine distances to approximate projection magnitudes.
    """
    # Convert everything into local offsets relative to origin
    # Δlat, Δlon but using km along each cardinal axis.
    # This avoids needing full 3D vectors.
    origin = (axis.origin_lat, axis.origin_lon)

    # Small displacements in km
    north_km = haversine_km(origin[0], origin[1], lat, origin[1])
    east_km  = haversine_km(origin[0], origin[1], origin[0], lon)

    # restore sign
    if lat < axis.origin_lat:
        north_km = -north_km
    if lon < axis.origin_lon:
        east_km = -east_km

    # Local point in the 2D plane
    px, py = north_km, east_km
    vx, vy = axis.dlat, axis.dlon  # direction vector in same space

    # projection length (dot product)
    along = px * vx + py * vy

    # perpendicular distance = |P - proj(P)| = |P - along * v|
    proj_x = along * vx
    proj_y = along * vy
    cross = ((px - proj_x)**2 + (py - proj_y)**2)**0.5

    return along, cross


# ---------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------

def build_direction_axis(frontline, direction_city: LocaleEntry) -> DirectionAxis:
    """
    Build the direction axis from the direction city toward the closest
    point on the frontline.
    """
    lat0 = direction_city.lat
    lon0 = direction_city.lon

    # Get nearest point on frontline geometry
    near_lat, near_lon = frontline.closest_point(lat0, lon0)

    dlat = near_lat - lat0
    dlon = near_lon - lon0
    ndlat, ndlon = _normalize_vector(dlat, dlon)

    return DirectionAxis(origin_lat=lat0, origin_lon=lon0, dlat=ndlat, dlon=ndlon)


def annotate_direction_axis_for_candidates(
    axis: DirectionAxis,
    candidates: Sequence[LocaleCandidate],
    *,
    label: str | None = None,
) -> None:
    """
    Mutates each LocaleCandidate's .scores with:
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
    event: Event,
    frontline,
    direction_city: LocaleEntry,
    *,
    label: str | None = None,
) -> Optional[DirectionAxis]:
    """
    Compute direction axis for an entire event, annotate all candidates.
    Return the DirectionAxis or None if event has no candidate locations.
    """
    # Collect all candidates across all Location objects
    all_candidates = []
    for loc in event.locations:
        all_candidates.extend(loc.candidates)

    if not all_candidates:
        return None

    axis = build_direction_axis(frontline, direction_city)
    annotate_direction_axis_for_candidates(axis, all_candidates, label=label)
    return axis
