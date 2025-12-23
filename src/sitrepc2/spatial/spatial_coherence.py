from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from statistics import median

from sitrepc2.spatial.distance import haversine_km
from sitrepc2.dom.nodes import (
    LocationSeriesNode,
    LocationNode,
    LocationCandidateNode,
)


# ============================================================
# DATA STRUCTURES (PURE SIGNALS / DIAGNOSTICS)
# ============================================================

@dataclass(frozen=True)
class SpatialSignals:
    """
    Candidate-level spatial coherence signals.

    All values are raw metrics. No normalization, no confidence,
    no interpretation beyond relative comparison.
    """

    centroid_distance_km: Optional[float] = None
    dispersion_delta_km: Optional[float] = None
    peer_median_distance_km: Optional[float] = None
    anchor_distance_km: Optional[float] = None


@dataclass(frozen=True)
class SeriesDiagnostics:
    """
    Series-level diagnostics for explanation and UI.
    Never folded automatically into confidence.
    """

    bbox_diagonal_km: Optional[float]
    median_pairwise_km: Optional[float]
    has_multiple_clusters: bool = False


# ============================================================
# GEOMETRY HELPERS (INTERNAL)
# ============================================================

def _coord(cand: LocationCandidateNode) -> Optional[Tuple[float, float]]:
    if cand.lat is None or cand.lon is None:
        return None
    return float(cand.lat), float(cand.lon)


def _bbox_diagonal(coords: List[Tuple[float, float]]) -> Optional[float]:
    if not coords:
        return None
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    return haversine_km(min(lats), min(lons), max(lats), max(lons))


def _centroid(coords: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    if not coords:
        return None
    lat = sum(c[0] for c in coords) / len(coords)
    lon = sum(c[1] for c in coords) / len(coords)
    return lat, lon


def _median_pairwise(coords: List[Tuple[float, float]]) -> Optional[float]:
    if len(coords) < 2:
        return None

    dists: List[float] = []
    for i in range(len(coords)):
        lat1, lon1 = coords[i]
        for j in range(i + 1, len(coords)):
            lat2, lon2 = coords[j]
            dists.append(haversine_km(lat1, lon1, lat2, lon2))

    return median(dists) if dists else None


# ============================================================
# CORE SPATIAL COHERENCE ANALYSIS
# ============================================================

def analyze_spatial_coherence(
    *,
    series: LocationSeriesNode,
    anchors: Optional[List[Tuple[float, float]]] = None,
) -> Tuple[
    Dict[LocationCandidateNode, SpatialSignals],
    SeriesDiagnostics,
]:
    """
    Analyze spatial coherence for a LocationSeries.

    Returns:
        (candidate_signals, series_diagnostics)

    Guarantees:
    - No selection
    - No assignment
    - No mutation
    - Candidate-centric signals only
    """

    anchors = anchors or []

    # --------------------------------------------------------
    # Collect all candidates and coordinates
    # --------------------------------------------------------

    all_candidates: List[LocationCandidateNode] = []
    candidate_coords: Dict[LocationCandidateNode, Tuple[float, float]] = {}

    for child in series.children:
        if not isinstance(child, LocationNode):
            continue

        for cand in child.children:
            if not isinstance(cand, LocationCandidateNode):
                continue

            coord = _coord(cand)
            if coord is not None:
                all_candidates.append(cand)
                candidate_coords[cand] = coord

    # --------------------------------------------------------
    # Degenerate cases: < 2 locations → no clustering signals
    # --------------------------------------------------------

    distinct_locations = {
        cand.parent for cand in all_candidates if cand.parent is not None
    }

    if len(distinct_locations) < 2:
        signals = {
            cand: SpatialSignals(
                anchor_distance_km=_anchor_distance(cand, anchors)
            )
            for cand in all_candidates
        }

        diagnostics = SeriesDiagnostics(
            bbox_diagonal_km=None,
            median_pairwise_km=None,
            has_multiple_clusters=False,
        )
        return signals, diagnostics

    # --------------------------------------------------------
    # Compute series-wide reference geometry
    # --------------------------------------------------------

    coords = list(candidate_coords.values())

    centroid = _centroid(coords)
    bbox_diag = _bbox_diagonal(coords)
    median_pairwise = _median_pairwise(coords)

    # Heuristic diagnostic only (never feeds confidence directly)
    has_multiple_clusters = (
        median_pairwise is not None and bbox_diag is not None
        and bbox_diag > 2.5 * median_pairwise
    )

    diagnostics = SeriesDiagnostics(
        bbox_diagonal_km=bbox_diag,
        median_pairwise_km=median_pairwise,
        has_multiple_clusters=has_multiple_clusters,
    )

    # --------------------------------------------------------
    # Candidate-level signal extraction
    # --------------------------------------------------------

    signals: Dict[LocationCandidateNode, SpatialSignals] = {}

    for cand, (lat, lon) in candidate_coords.items():

        # --- Centroid proximity ---
        centroid_dist = None
        if centroid is not None:
            centroid_dist = haversine_km(lat, lon, centroid[0], centroid[1])

        # --- Peer median distance ---
        peer_dists: List[float] = []
        for other, (olat, olon) in candidate_coords.items():
            if other is cand:
                continue
            peer_dists.append(haversine_km(lat, lon, olat, olon))

        peer_median = median(peer_dists) if peer_dists else None

        # --- Dispersion contribution ---
        dispersion_delta = None
        if median_pairwise is not None and peer_median is not None:
            dispersion_delta = peer_median - median_pairwise

        # --- Anchor proximity ---
        anchor_dist = _anchor_distance(cand, anchors)

        signals[cand] = SpatialSignals(
            centroid_distance_km=centroid_dist,
            dispersion_delta_km=dispersion_delta,
            peer_median_distance_km=peer_median,
            anchor_distance_km=anchor_dist,
        )

    return signals, diagnostics


# ============================================================
# ANCHOR SUPPORT
# ============================================================

def _anchor_distance(
    cand: LocationCandidateNode,
    anchors: Iterable[Tuple[float, float]],
) -> Optional[float]:
    coord = _coord(cand)
    if coord is None or not anchors:
        return None

    lat, lon = coord
    dists = [
        haversine_km(lat, lon, alat, alon)
        for alat, alon in anchors
    ]
    return min(dists) if dists else None
