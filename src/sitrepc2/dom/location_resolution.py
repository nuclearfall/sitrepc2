from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

from sitrepc2.dom.nodes import LocationNode, LocationCandidateNode
from sitrepc2.dom.candidate_confidence import (
    LocationConfidenceResult,
    CandidateConfidence,
)


# ============================================================
# PROCEDURAL RESOLUTION STATES
# ============================================================

class ResolutionState(Enum):
    """
    Procedural resolution state for a LocationNode.

    These states govern pipeline eligibility only.
    They do NOT assert correctness.
    """

    RESOLVED = "resolved"       # Eligible to proceed automatically
    AMBIGUOUS = "ambiguous"     # User action required
    UNRESOLVED = "unresolved"   # Must not be committed


# ============================================================
# CONFIGURATION (POLICY, NOT SEMANTICS)
# ============================================================

@dataclass(frozen=True)
class ResolutionPolicy:
    """
    Tunable policy parameters governing procedural resolution.

    These values may be adjusted without changing semantics.
    """

    # Minimum confidence required for top candidate to be viable
    confidence_floor: float = 0.6

    # Minimum gap between top two candidates
    dominance_gap: float = 0.25


# ============================================================
# RESULT STRUCTURE
# ============================================================

@dataclass(frozen=True)
class LocationResolutionResult:
    """
    Procedural resolution outcome for a LocationNode.
    """

    location: LocationNode
    state: ResolutionState
    top_candidate: LocationCandidateNode | None
    confidence_gap: float | None


# ============================================================
# CORE RESOLUTION LOGIC (PHASE 5d-B)
# ============================================================

def determine_location_resolution(
    *,
    confidence_result: LocationConfidenceResult,
    policy: ResolutionPolicy = ResolutionPolicy(),
) -> LocationResolutionResult:
    """
    Determine procedural resolution state for a LocationNode.

    Guarantees:
    - No selection
    - No mutation
    - No commitment
    - User remains final authority
    """

    ordered = confidence_result.ordered_candidates
    location = confidence_result.location

    # --------------------------------------------------------
    # No candidates → unresolved
    # --------------------------------------------------------

    if not ordered:
        return LocationResolutionResult(
            location=location,
            state=ResolutionState.UNRESOLVED,
            top_candidate=None,
            confidence_gap=None,
        )

    # --------------------------------------------------------
    # Single candidate → procedurally resolved
    # --------------------------------------------------------

    if len(ordered) == 1:
        cand, _conf = ordered[0]
        return LocationResolutionResult(
            location=location,
            state=ResolutionState.RESOLVED,
            top_candidate=cand,
            confidence_gap=None,
        )

    # --------------------------------------------------------
    # Multiple candidates → dominance analysis
    # --------------------------------------------------------

    (top_cand, top_conf), (next_cand, next_conf) = ordered[:2]

    gap = top_conf.score - next_conf.score

    # Top confidence too low
    if top_conf.score < policy.confidence_floor:
        return LocationResolutionResult(
            location=location,
            state=ResolutionState.AMBIGUOUS,
            top_candidate=None,
            confidence_gap=gap,
        )

    # Gap too small → ambiguity
    if gap < policy.dominance_gap:
        return LocationResolutionResult(
            location=location,
            state=ResolutionState.AMBIGUOUS,
            top_candidate=None,
            confidence_gap=gap,
        )

    # --------------------------------------------------------
    # Dominant candidate exists → procedurally resolved
    # --------------------------------------------------------

    return LocationResolutionResult(
        location=location,
        state=ResolutionState.RESOLVED,
        top_candidate=top_cand,
        confidence_gap=gap,
    )
