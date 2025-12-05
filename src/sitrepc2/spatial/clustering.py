# src/modmymap/nlp/clustering.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from mip import BINARY, Model, OptimizationStatus, xsum

from sitrepc2.gazetter.lookup import LocaleEntry  # adjust import if LocaleEntry is in a different module
from sitrepc2.nlp.dataclasses import (
    LocationKind,
    EventEventLocationMention,
    LocaleCandidate,
)

Coord = Tuple[float, float]  # (lat, lon)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ClusterDiagnostics:
    """
    Diagnostics and contextual signals for a chosen cluster.

    Cluster-level; you can fan these back into per-mention ContextSignals.
    """

    # Approximate diagonal of the bounding box covering all chosen locales.
    bbox_diagonal_km: float

    # True if bbox_diagonal_km exceeds the "weirdly large" threshold.
    bbox_is_large: bool

    # Mention IDs that are geographic outliers relative to the cluster centroid.
    outlier_mention_ids: list[str] = field(default_factory=list)

    # Duplicate selections: mapping Wikidata QID -> list of mention_ids that
    # ended up resolving to that QID. Only entries with len(...) > 1 are kept.
    duplicate_qid_groups: Dict[str, list[str]] = field(default_factory=dict)

    # structural outliers (for enrichment / Overpass)
    structural_outlier_ids: list[str] = field(default_factory=list)


@dataclass
class ClusterChoice:
    """
    Result of joint disambiguation across a series of EventLocationMentions.
    """

    # For each mention_id, which candidate was selected.
    assignments: Dict[str, LocaleCandidateRecord]

    # Cluster score (higher is better). Purely relative; only meaningful when
    # comparing alternative clusters produced by this utility.
    score: float

    # Cluster-level diagnostics (bbox size, outliers, duplicates).
    diagnostics: ClusterDiagnostics


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _candidate_coord(candidate: LocaleCandidateRecord) -> Coord:
    """
    Extract (lat, lon) from a LocaleCandidateRecord.

    Assumes candidate.entry is a LocaleEntry-like object with .lat and .lon
    attributes in decimal degrees.
    """
    entry = candidate.entry
    lat = getattr(entry, "lat")
    lon = getattr(entry, "lon")
    return float(lat), float(lon)


def _candidate_region_key(candidate: LocaleCandidateRecord) -> str | None:
    """
    Extract a region-like key (typically oblast name) from a candidate.

    Adjust this to match your LocaleEntry fields if needed.
    """
    entry = candidate.entry
    if hasattr(entry, "oblast_en"):
        return getattr(entry, "oblast_en") or None
    if hasattr(entry, "region"):
        return getattr(entry, "region") or None
    return None


def _candidate_ru_group(candidate: LocaleCandidateRecord) -> str | None:
    """
    Extract ru_group (operational group area) from a candidate, if present.
    """
    entry = candidate.entry
    return getattr(entry, "ru_group", None)


def _candidate_qid(candidate: LocaleCandidateRecord) -> str | None:
    """
    Extract a Wikidata QID from a candidate.

    Tries .wikidata first, then .qid as a fallback.
    """
    entry = candidate.entry
    qid = getattr(entry, "wikidata", None)
    if qid is None and hasattr(entry, "qid"):
        qid = getattr(entry, "qid")
    return qid


def _cluster_bbox_diagonal(coords: Iterable[Coord]) -> float:
    """
    Approximate bbox diagonal (in km) for a set of (lat, lon) points.
    """
    coords = list(coords)
    if not coords:
        return 0.0

    lats = [lat for lat, _ in coords]
    lons = [lon for _, lon in coords]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    return haversine_km(min_lat, min_lon, max_lat, max_lon)


def _cluster_centroid(coords: Mapping[str, Coord]) -> Coord:
    """
    Simple arithmetic centroid in lat/lon space.
    """
    if not coords:
        return 0.0, 0.0

    lats = [lat for lat, _ in coords.values()]
    lons = [lon for _, lon in coords.values()]
    return sum(lats) / len(lats), sum(lons) / len(lons)

def _cluster_compactness(coords: Mapping[str, Coord]) -> float:
    """
    Measure cluster compactness: smaller = tighter.

    We use the median of all pairwise distances. This is robust to
    individual long edges but still reflects overall spread.
    """
    dists = _pairwise_distances(coords)
    if not dists:
        return 0.0
    return median(dists)

def _pairwise_distances(coords: Mapping[str, Coord]) -> list[float]:
    """
    All pairwise distances between the given coordinates (in km).
    """
    ids = list(coords.keys())
    out: list[float] = []
    for i in range(len(ids)):
        mid_i = ids[i]
        lat_i, lon_i = coords[mid_i]
        for j in range(i + 1, len(ids)):
            mid_j = ids[j]
            lat_j, lon_j = coords[mid_j]
            out.append(haversine_km(lat_i, lon_i, lat_j, lon_j))
    return out

def _compute_structural_outliers(
    assignments: Mapping[str, LocaleCandidateRecord],
    *,
    improvement_factor_threshold: float = 0.35,
    min_removed_improvement_km: float = 5.0,
) -> list[str]:
    """
    Identify structural outliers: points whose removal causes the remaining
    cluster to become *much* more compact.

    - improvement_factor_threshold:
        relative improvement threshold, e.g. 0.35 means "removing this
        point reduces the median pairwise distance by at least 35%".
    - min_removed_improvement_km:
        minimal absolute improvement in km required to consider it a real
        effect, not just noise.
    """
    # Build coords map for convenience.
    coords: Dict[str, Coord] = {
        mid: _candidate_coord(cand) for mid, cand in assignments.items()
    }
    if len(coords) <= 2:
        # With 1–2 points, there's no meaningful "structural outlier".
        return []

    base_compact = _cluster_compactness(coords)
    if base_compact <= 0:
        return []

    structural_outliers: list[str] = []

    for mid in list(coords.keys()):
        coords_minus = dict(coords)
        coords_minus.pop(mid, None)
        if len(coords_minus) <= 1:
            continue

        compact_minus = _cluster_compactness(coords_minus)
        improvement = base_compact - compact_minus  # positive = tighter after removal

        # Relative improvement (fractional reduction in median distance).
        improvement_factor = improvement / base_compact

        if (
            improvement > min_removed_improvement_km
            and improvement_factor > improvement_factor_threshold
        ):
            structural_outliers.append(mid)

    return structural_outliers

def _compute_diagnostics(
    assignments: Mapping[str, LocaleCandidateRecord],
    *,
    max_bbox_km: float,
) -> ClusterDiagnostics:
    """
    Compute bbox, outliers, and duplicate QID signals for a fully specified cluster.
    """
    coords: Dict[str, Coord] = {
        mention_id: _candidate_coord(candidate)
        for mention_id, candidate in assignments.items()
    }

    bbox_diagonal_km = _cluster_bbox_diagonal(coords.values())
    bbox_is_large = bbox_diagonal_km > max_bbox_km

    centroid_lat, centroid_lon = _cluster_centroid(coords)
    distances_to_centroid: Dict[str, float] = {
        mention_id: haversine_km(lat, lon, centroid_lat, centroid_lon)
        for mention_id, (lat, lon) in coords.items()
    }

    if distances_to_centroid:
        dist_values = list(distances_to_centroid.values())
        med = median(dist_values)
        # Outlier: far from centroid AND further than a reasonable absolute threshold.
        outlier_threshold = max(max_bbox_km, 2.0 * med)
        outlier_mention_ids = [
            mid
            for mid, d in distances_to_centroid.items()
            if d > outlier_threshold
        ]
    else:
        outlier_mention_ids = []

    # Duplicate QIDs.
    qid_to_mentions: Dict[str, list[str]] = {}
    for mention_id, candidate in assignments.items():
        qid = _candidate_qid(candidate)
        if not qid:
            continue
        qid_to_mentions.setdefault(qid, []).append(mention_id)

    duplicate_qid_groups = {
        qid: mids for qid, mids in qid_to_mentions.items() if len(mids) > 1
    }

    structural_outlier_ids = _compute_structural_outliers(assignments)

    return ClusterDiagnostics(
        bbox_diagonal_km=bbox_diagonal_km,
        bbox_is_large=bbox_is_large,
        outlier_mention_ids=outlier_mention_ids,
        duplicate_qid_groups=duplicate_qid_groups,
        structural_outlier_ids=structural_outlier_ids,
    )


# ---------------------------------------------------------------------------
# Unary scoring (frontline distance)
# ---------------------------------------------------------------------------


def unary_direction_score(
    cand: LocaleCandidateRecord,
    *,
    cross_full_score_km: float = 8.0,
    cross_zero_score_km: float = 20.0,
    along_min_km: float = -10.0,   # tolerate a bit "behind" city
    along_max_km: float = 60.0,    # don't reward way beyond LoC
) -> float:
    """
    Optional unary term based on “direction of X” axis metrics.

    Intuition:
    - Small cross_axis distance → strong positive.
    - Very large cross_axis distance → negative.
    - along_axis outside reasonable band → downweight / penalize.
    """
    if getattr(cand, "dir_cross_km", None) is None:
        return 0.0

    cross = cand.dir_cross_km
    along = cand.dir_along_km

    # Lateral component: prefer close to the axis.
    if cross <= cross_full_score_km:
        lateral = 1.0
    elif cross <= cross_zero_score_km:
        lateral = 1.0 - (cross - cross_full_score_km) / (
            cross_zero_score_km - cross_full_score_km
        )  # → 0
    else:
        # Gently negative if way off-axis.
        overflow = cross - cross_zero_score_km
        lateral = -min(overflow / cross_zero_score_km, 1.0)

    # Along-axis sanity gating.
    along_factor = 1.0
    if along is not None:
        if along < along_min_km or along > along_max_km:
            # way behind the city or way too far past "normal" range
            along_factor = 0.3

    # Weight so it’s important, but not insane compared to frontline term.
    return 1.0 * lateral * along_factor



def unary_score(cand: LocaleCandidateRecord) -> float:
    """
    Aggregate unary score for a candidate.

    Currently:
    - frontline distance
    - optional direction-axis consistency (if available)
    """
    return unary_frontline_score(cand) + unary_direction_score(cand)



# ---------------------------------------------------------------------------
# Pairwise coherence scoring (cluster compactness + region/ru_group)
# ---------------------------------------------------------------------------


def _pairwise_score(
    cand_a: LocaleCandidateRecord,
    cand_b: LocaleCandidateRecord,
    *,
    compactness_weight: float = 2.0,
    close_km: float = 15.0,
    far_km: float = 50.0,
    region_same_weight: float = 1.0,
    region_mismatch_penalty: float = 1.0,
    ru_same_weight: float = 0.5,
    ru_mismatch_penalty: float = 0.25,
) -> float:
    """
    Pairwise coherence score: region/ru_group + geometric compactness.

    Goals:
    - Strongly reward tight clusters (Shevchenko + Yampil + Torske).
    - Penalize far-flung outliers (Sumy Shevchenko far from everything else),
      even if they are very close to the LoC.
    - Region/ru_group coherence are important but secondary to tight grouping.

    Compactness behavior:
      d <= close_km        → strong positive (+compactness_weight)
      close_km–far_km      → fades towards 0
      d > far_km           → negative, down to about -compactness_weight
    """
    score = 0.0

    # Region coherence ------------------------------------------------------
    reg_a = _candidate_region_key(cand_a)
    reg_b = _candidate_region_key(cand_b)
    if reg_a is not None and reg_b is not None:
        if reg_a == reg_b:
            score += region_same_weight
        else:
            score -= region_mismatch_penalty

    # RU group coherence ----------------------------------------------------
    ru_a = _candidate_ru_group(cand_a)
    ru_b = _candidate_ru_group(cand_b)
    if ru_a is not None and ru_b is not None:
        if ru_a == ru_b:
            score += ru_same_weight
        else:
            score -= ru_mismatch_penalty

    # Geometric compactness -------------------------------------------------
    (lat_a, lon_a) = _candidate_coord(cand_a)
    (lat_b, lon_b) = _candidate_coord(cand_b)
    d_km = haversine_km(lat_a, lon_a, lat_b, lon_b)

    if d_km <= close_km:
        # Very tight cluster: full positive compactness.
        compact = 1.0
    elif d_km <= far_km:
        # Gradual fade from +1 down to 0.
        compact = 1.0 - (d_km - close_km) / (far_km - close_km)
    else:
        # Beyond far_km: increasingly negative up to -1.0.
        overflow = d_km - far_km
        compact = -min(overflow / far_km, 1.0)

    score += compactness_weight * compact

    return score


# ---------------------------------------------------------------------------
# Public API (MIP-based cluster selection)
# ---------------------------------------------------------------------------


def choose_best_locale_cluster(
    mentions: Sequence[EventLocationMention],
    *,
    max_bbox_km: float = 30.0,
    close_km: float = 15.0,
    far_km: float = 50.0,
    mip_time_limit_sec: float | None = None,
) -> ClusterChoice | None:
    """
    Jointly choose one locale candidate per EventLocationMention using a MILP model
    solved via python-mip.

    - Only LocationKind.LOCALE mentions with non-empty locale_candidates
      are considered.
    - Mentions with exactly 1 candidate are treated as fixed anchors logically
      (the MIP still sees them, but there is no real branching).
    - Mentions with multiple candidates are jointly disambiguated.
    - Duplicate QIDs across mentions are allowed but recorded in diagnostics.

    Objective components:
      Unary:
        - Frontline distance via cand.distance_loc (strong but bounded).
      Pairwise:
        - Geometric compactness (dominant for outlier suppression).
        - Region coherence (oblast).
        - RU group coherence (operational group).

    Returns:
        ClusterChoice with assignments, score, and diagnostics,
        or None if no usable mentions or the model is infeasible.
    """
    # Filter to LOCALE mentions with candidates.
    usable: list[EventLocationMention] = [
        m
        for m in mentions
        if m.kind is LocationKind.LOCALE and m.locale_candidates
    ]

    if not usable:
        return None

    # Index mentions consistently.
    index_to_mention: Dict[int, EventLocationMention] = {
        idx: m for idx, m in enumerate(usable)
    }
    n_mentions = len(usable)

    candidates_per_mention: Dict[int, Sequence[LocaleCandidateRecord]] = {
        idx: tuple(m.locale_candidates) for idx, m in index_to_mention.items()
    }

    # Build model.
    model = Model(sense="MAX")  # maximize coherence
    if mip_time_limit_sec is not None:
        model.max_seconds = mip_time_limit_sec

    # Decision variables: x[i][j] = 1 if candidate j of mention i is chosen.
    x: Dict[int, list] = {}
    for i in range(n_mentions):
        cands = candidates_per_mention[i]
        x[i] = [model.add_var(var_type=BINARY) for _ in range(len(cands))]

    # Each mention must pick exactly one candidate.
    for i in range(n_mentions):
        model += xsum(x[i][j] for j in range(len(candidates_per_mention[i]))) == 1

    # Unary terms: frontline distance etc.
    unary_terms = []
    for i in range(n_mentions):
        cands = candidates_per_mention[i]
        for j, cand in enumerate(cands):
            s = unary_score(cand)
            if s != 0.0:
                unary_terms.append(s * x[i][j])

    # Pairwise terms: compactness + region/ru_group coherence.
    pairwise_terms = []
    y_vars = {}  # (i, j, k, l) -> y_var

    for i in range(n_mentions):
        cands_i = candidates_per_mention[i]
        for k in range(i + 1, n_mentions):
            cands_k = candidates_per_mention[k]
            for j, cand_i in enumerate(cands_i):
                for l, cand_k in enumerate(cands_k):
                    score_ik = _pairwise_score(
                        cand_i,
                        cand_k,
                        close_km=close_km,
                        far_km=far_km,
                    )
                    if score_ik == 0.0:
                        # Skip zero-score pairs to reduce model size slightly.
                        continue

                    y = model.add_var(var_type=BINARY)
                    y_vars[(i, j, k, l)] = y

                    # Linearization constraints: y = x[i][j] AND x[k][l].
                    model += y <= x[i][j]
                    model += y <= x[k][l]
                    model += y >= x[i][j] + x[k][l] - 1

                    pairwise_terms.append(score_ik * y)

    # Objective = unary + pairwise
    if unary_terms or pairwise_terms:
        model.objective = xsum(unary_terms) + xsum(pairwise_terms)
    else:
        # Degenerate case: no scoring terms; any assignment works.
        model.objective = xsum([])

    # Solve.
    status = model.optimize()

    if status not in (OptimizationStatus.OPTIMAL, OptimizationStatus.FEASIBLE):
        # No reasonable solution.
        return None

    # Extract chosen candidates.
    assignments: Dict[str, LocaleCandidateRecord] = {}
    for i, mention in index_to_mention.items():
        chosen_idx = None
        for j, var in enumerate(x[i]):
            if var.x is not None and var.x >= 0.99:
                chosen_idx = j
                break
        if chosen_idx is None:
            # Safety fallback: should not happen if model is correct.
            chosen_idx = 0
        chosen_cand = candidates_per_mention[i][chosen_idx]
        assignments[mention.mention_id] = chosen_cand

    # NEW: compute per-candidate confidence for the chosen candidates
    #      based on the same unary + pairwise scoring used in the MIP.
    for mid, cand in assignments.items():
        # Unary component (frontline distance, etc.)
        unary = unary_score(cand)

        # Pairwise component: coherence with all *other* chosen candidates.
        pairwise = 0.0
        for other_mid, other_cand in assignments.items():
            if other_mid == mid:
                continue
            pairwise += _pairwise_score(
                cand,
                other_cand,
                close_km=close_km,
                far_km=far_km,
            )

        # Store final per-candidate confidence on the record itself.
        cand.confidence = unary + pairwise

    score = float(model.objective_value or 0.0)

    diagnostics = _compute_diagnostics(assignments, max_bbox_km=max_bbox_km)

    return ClusterChoice(
        assignments=assignments,
        score=score,
        diagnostics=diagnostics,
    )
