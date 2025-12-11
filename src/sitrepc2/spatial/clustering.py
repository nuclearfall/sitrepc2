# src/sitrepc2/spatial/clustering.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from statistics import median
from math import inf

from sitrepc2.spatial.distance import haversine_km
from sitrepc2.gazetteer.typedefs import LocaleEntry
from sitrepc2.dom.typedefs import Location, LocaleCandidate


# =====================================================
#  CONFIGURATION: SCORING PARAMETERS
# =====================================================

@dataclass
class ClusterScoring:
    """
    Configurable scoring parameters for unary and pairwise scoring.
    Defaults are set to match the original MIP behaviour.
    """

    # Unary contributions
    frontline_weight: float = 1.0
    direction_weight: float = 1.0

    # Pairwise compactness
    compactness_weight: float = 2.0
    close_km: float = 15.0
    far_km: float = 50.0

    # Region and RU group coherence
    region_same_weight: float = 1.0
    region_mismatch_penalty: float = 1.0
    ru_same_weight: float = 0.5
    ru_mismatch_penalty: float = 0.25


# =====================================================
#  CLUSTER DIAGNOSTICS
# =====================================================

@dataclass
class ClusterDiagnostics:
    bbox_diagonal_km: float
    bbox_is_large: bool
    outlier_location_ids: List[int] = field(default_factory=list)
    duplicate_qid_groups: Dict[str, List[int]] = field(default_factory=dict)
    structural_outlier_ids: List[int] = field(default_factory=list)


@dataclass
class ClusterChoice:
    assignments: Dict[int, LocaleCandidate]
    score: float
    diagnostics: ClusterDiagnostics


# =====================================================
#  INTERNAL HELPERS
# =====================================================

def _coord(cand: LocaleCandidate) -> Tuple[float, float]:
    """Return (lat, lon) from the LocaleEntry contained inside the candidate."""
    loc: LocaleEntry = cand.locale
    return float(loc.lat), float(loc.lon)


def _qid(cand: LocaleCandidate) -> Optional[str]:
    """Return Wikidata QID if available."""
    q = getattr(cand.locale, "wikidata", None)
    return q or None


def _cluster_bbox_diagonal(coords: Sequence[Tuple[float, float]]) -> float:
    if not coords:
        return 0.0
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    return haversine_km(min(lats), min(lons), max(lats), max(lons))


def _cluster_centroid(coords: Dict[int, Tuple[float, float]]) -> Tuple[float, float]:
    if not coords:
        return (0.0, 0.0)
    lat = sum(c[0] for c in coords.values()) / len(coords)
    lon = sum(c[1] for c in coords.values()) / len(coords)
    return lat, lon


def _median_pairwise(coords: Dict[int, Tuple[float, float]]) -> float:
    """Median pairwise distance, robust compactness metric."""
    keys = list(coords.keys())
    N = len(keys)
    if N <= 1:
        return 0.0
    dists = []
    for i in range(N):
        lat_i, lon_i = coords[keys[i]]
        for j in range(i+1, N):
            lat_j, lon_j = coords[keys[j]]
            dists.append(haversine_km(lat_i, lon_i, lat_j, lon_j))
    return median(dists) if dists else 0.0


def _compute_structural_outliers(assignments: Dict[int, LocaleCandidate]) -> List[int]:
    """
    Structural outlier = removing that location dramatically tightens the cluster.
    """
    coords = {mid: _coord(c) for mid, c in assignments.items()}
    if len(coords) <= 2:
        return []

    base_compact = _median_pairwise(coords)
    if base_compact <= 0:
        return []

    out = []
    for mid in list(coords.keys()):
        reduced = dict(coords)
        reduced.pop(mid, None)
        if len(reduced) <= 1:
            continue
        reduced_compact = _median_pairwise(reduced)
        improvement = base_compact - reduced_compact
        if improvement > 5.0 and improvement / base_compact > 0.35:
            out.append(mid)
    return out


# =====================================================
#  SCORING FUNCTIONS
# =====================================================

def unary_score(cand: LocaleCandidate, scoring: ClusterScoring) -> float:
    """
    Compute unary score: frontline + direction.
    cand.distance_from_frontline_km
    cand.scores["dir_cross_km"], cand.scores["dir_along_km"] if available.
    """

    score = 0.0

    # Frontline: closer = better.
    dfl = getattr(cand, "distance_from_frontline_km", None)
    if dfl is not None:
        # Negative slope: closer gives higher score.
        score += scoring.frontline_weight * max(0.0, 50.0 - dfl) / 50.0

    # Direction scoring (if available)
    cross = cand.scores.get("dir_cross_km")
    along = cand.scores.get("dir_along_km")
    if cross is not None:
        if cross <= 8:
            lat_term = 1.0
        elif cross <= 20:
            lat_term = 1.0 - (cross - 8) / 12.0
        else:
            lat_term = -min((cross - 20) / 20.0, 1.0)

        along_term = 1.0
        if along is not None and (along < -10 or along > 60):
            along_term = 0.3

        score += scoring.direction_weight * lat_term * along_term

    return score


def pairwise_score(
    cand_a: LocaleCandidate,
    cand_b: LocaleCandidate,
    scoring: ClusterScoring,
) -> float:
    """
    Pairwise coherence:
      - region alignment
      - ru_group alignment
      - geographic compactness
    """
    score = 0.0
    a, b = cand_a.locale, cand_b.locale

    # Region coherence
    if a.region and b.region:
        if a.region == b.region:
            score += scoring.region_same_weight
        else:
            score -= scoring.region_mismatch_penalty

    # RU group coherence
    if a.ru_group and b.ru_group:
        if a.ru_group == b.ru_group:
            score += scoring.ru_same_weight
        else:
            score -= scoring.ru_mismatch_penalty

    # Geometric compactness
    (lat_a, lon_a) = _coord(cand_a)
    (lat_b, lon_b) = _coord(cand_b)
    d = haversine_km(lat_a, lon_a, lat_b, lon_b)

    if d <= scoring.close_km:
        compact = 1.0
    elif d <= scoring.far_km:
        compact = 1.0 - (d - scoring.close_km) / (scoring.far_km - scoring.close_km)
    else:
        compact = -min((d - scoring.far_km) / scoring.far_km, 1.0)

    score += scoring.compactness_weight * compact
    return score


def partial_assignment_score(
    assignment: Dict[int, LocaleCandidate],
    scoring: ClusterScoring
) -> float:
    """
    Compute total score for a partial assignment using all unary terms and
    pairwise terms where both sides are already assigned.
    """
    total = 0.0

    # Unary
    for c in assignment.values():
        total += unary_score(c, scoring)

    # Pairwise
    keys = list(assignment.keys())
    N = len(keys)
    for i in range(N):
        for j in range(i+1, N):
            total += pairwise_score(assignment[keys[i]], assignment[keys[j]], scoring)

    return total


# =====================================================
#  MAIN BEAM-SEARCH CLUSTERING ALGORITHM
# =====================================================

def cluster_locations(
    locations: Sequence[Location],
    *,
    scoring: ClusterScoring = ClusterScoring(),
    beam_width: int = 50,
    max_bbox_km: float = 30.0,
) -> Optional[ClusterChoice]:
    """
    Resolve one candidate per Location using a deterministic beam-search.
    Returns ClusterChoice(assignments, score, diagnostics) or None.
    """

    # Filter to only locations with candidates.
    usable = [(idx, loc) for idx, loc in enumerate(locations) if loc.candidates]
    if not usable:
        return None

    # Identify anchors (only 1 candidate).
    anchors = {idx: loc.candidates[0] for idx, loc in usable if len(loc.candidates) == 1}
    variables = [(idx, loc) for idx, loc in usable if idx not in anchors]

    # Beam starts with a single partial assignment = anchors.
    beam: List[Tuple[Dict[int, LocaleCandidate], float]] = [(anchors, partial_assignment_score(anchors, scoring))]

    # Expand beam for each variable location.
    for idx, loc in variables:
        new_beam = []
        for assignment, score_so_far in beam:
            for cand in loc.candidates:
                new_assign = dict(assignment)
                new_assign[idx] = cand
                scr = partial_assignment_score(new_assign, scoring)
                new_beam.append((new_assign, scr))

        # Keep top-K
        new_beam.sort(key=lambda x: x[1], reverse=True)
        beam = new_beam[:beam_width]

    if not beam:
        return None

    # Best full assignment
    best_assignment, best_score = beam[0]

    # Compute diagnostics
    coords = [_coord(c) for c in best_assignment.values()]
    bbox = _cluster_bbox_diagonal(coords)
    bbox_is_large = bbox > max_bbox_km

    centroid = _cluster_centroid({i: _coord(c) for i, c in best_assignment.items()})
    outliers = []
    for i, cand in best_assignment.items():
        lat, lon = _coord(cand)
        d = haversine_km(lat, lon, centroid[0], centroid[1])
        if d > max_bbox_km:
            outliers.append(i)

    # Duplicate QIDs
    qid_groups: Dict[str, List[int]] = {}
    for i, cand in best_assignment.items():
        q = _qid(cand)
        if q:
            qid_groups.setdefault(q, []).append(i)
    dupes = {k: v for k, v in qid_groups.items() if len(v) > 1}

    # Structural outliers
    structural = _compute_structural_outliers(best_assignment)

    diagnostics = ClusterDiagnostics(
        bbox_diagonal_km=bbox,
        bbox_is_large=bbox_is_large,
        outlier_location_ids=outliers,
        duplicate_qid_groups=dupes,
        structural_outlier_ids=structural,
    )

    # Assign confidences using unary + pairwise against final cluster
    for i, cand in best_assignment.items():
        unary = unary_score(cand, scoring)
        pair = 0.0
        for j, other in best_assignment.items():
            if i == j:
                continue
            pair += pairwise_score(cand, other, scoring)
        cand.confidence = unary + pair

    return ClusterChoice(best_assignment, best_score, diagnostics)
