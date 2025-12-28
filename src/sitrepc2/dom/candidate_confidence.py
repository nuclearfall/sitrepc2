from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from sitrepc2.dom.nodes import (
    LocationNode,
    LocationCandidateNode,
)
from sitrepc2.dom.spatial_coherence import SpatialSignals


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass(frozen=True)
class CandidateConfidence:
    """
    Aggregated, candidate-centric confidence information.

    `score` is meaningful ONLY for ordering among siblings
    of the same LocationNode.
    """

    score: float
    signals: SpatialSignals


@dataclass(frozen=True)
class LocationConfidenceResult:
    """
    Result for a single LocationNode.
    """

    location: LocationNode
    ordered_candidates: List[Tuple[LocationCandidateNode, CandidateConfidence]]


# ============================================================
# CONFIDENCE AGGREGATION (PHASE 5d-A)
# ============================================================

def compute_candidate_confidence(
    *,
    location: LocationNode,
    spatial_signals: Dict[LocationCandidateNode, SpatialSignals],
) -> LocationConfidenceResult:
    """
    Compute candidate-level confidence ordering for a LocationNode.

    Guarantees:
    - No selection
    - No mutation
    - No resolution
    - Flat confidence where ambiguity exists
    """

    candidates = [
        c for c in location.children
        if isinstance(c, LocationCandidateNode)
    ]

    # --------------------------------------------------------
    # Structural dominance cases
    # --------------------------------------------------------

    # User-resolved candidate overrides everything
    resolved = [
        c for c in candidates
        if c.resolved_location_id is not None
    ]
    if resolved:
        ordered = [
            (c, CandidateConfidence(score=1.0, signals=spatial_signals.get(c, SpatialSignals())))
            for c in resolved
        ]
        return LocationConfidenceResult(location, ordered)

    # Single candidate → trivially high confidence
    if len(candidates) == 1:
        c = candidates[0]
        return LocationConfidenceResult(
            location,
            [(c, CandidateConfidence(score=1.0, signals=spatial_signals.get(c, SpatialSignals())))]
        )

    # --------------------------------------------------------
    # Ambiguous single-location case (multiple candidates)
    # --------------------------------------------------------

    # If this LocationNode is the only location in its series,
    # clustering-derived signals must not differentiate.
    series = location.parent
    if series is not None:
        sibling_locations = [
            n for n in series.children
            if isinstance(n, LocationNode)
        ]
    else:
        sibling_locations = []

    if len(sibling_locations) <= 1:
        # Flat ordering, equal confidence
        flat = [
            (c, CandidateConfidence(score=0.0, signals=spatial_signals.get(c, SpatialSignals())))
            for c in candidates
        ]
        return LocationConfidenceResult(location, flat)

    # --------------------------------------------------------
    # Multi-location confidence aggregation
    # --------------------------------------------------------

    raw_scores: Dict[LocationCandidateNode, float] = {}

    for c in candidates:
        sig = spatial_signals.get(c)
        score = 0.0

        if sig is None:
            raw_scores[c] = score
            continue

        # --- Centroid proximity (closer is better) ---
        if sig.centroid_distance_km is not None:
            score += _inverse_distance(sig.centroid_distance_km)

        # --- Peer consistency ---
        if sig.peer_median_distance_km is not None:
            score += _inverse_distance(sig.peer_median_distance_km)

        # --- Dispersion contribution ---
        if sig.dispersion_delta_km is not None:
            score -= sig.dispersion_delta_km

        # --- Anchor proximity ---
        if sig.anchor_distance_km is not None:
            score += _inverse_distance(sig.anchor_distance_km)

        raw_scores[c] = score

    # --------------------------------------------------------
    # Normalize locally for ordering only
    # --------------------------------------------------------

    ordered = _normalize_and_order(candidates, raw_scores, spatial_signals)
    return LocationConfidenceResult(location, ordered)


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _inverse_distance(d: float) -> float:
    """
    Soft inverse distance contribution.
    No singularities; bounded influence.
    """
    return 1.0 / (1.0 + d)


def _normalize_and_order(
    candidates: Iterable[LocationCandidateNode],
    raw_scores: Dict[LocationCandidateNode, float],
    spatial_signals: Dict[LocationCandidateNode, SpatialSignals],
) -> List[Tuple[LocationCandidateNode, CandidateConfidence]]:
    """
    Normalize scores *only* to allow relative ordering.
    """

    if not raw_scores:
        return []

    values = list(raw_scores.values())
    min_v = min(values)
    max_v = max(values)

    ordered: List[Tuple[LocationCandidateNode, CandidateConfidence]] = []

    for c in candidates:
        raw = raw_scores.get(c, 0.0)

        # Flat distribution → preserve ambiguity
        if max_v == min_v:
            norm = 0.0
        else:
            norm = (raw - min_v) / (max_v - min_v)

        ordered.append(
            (c, CandidateConfidence(score=norm, signals=spatial_signals.get(c, SpatialSignals())))
        )
    # Order by descending confidence
    ordered.sort(key=lambda x: x[1].score, reverse=True)
    return ordered
