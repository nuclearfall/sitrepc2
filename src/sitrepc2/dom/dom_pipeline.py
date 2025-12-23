from __future__ import annotations

from enum import Enum
from typing import Iterable

from sitrepc2.dom.nodes import PostNode, LocationNode
from sitrepc2.dom.dom_persistence import persist_dom_snapshot

from sitrepc2.dom.dom_filtering import filter_location_candidates
from sitrepc2.dom.spatial_coherence import compute_spatial_signals
from sitrepc2.dom.candidate_confidence import compute_candidate_confidence
from sitrepc2.dom.location_resolution import determine_location_resolution


# ============================================================
# PIPELINE PHASE ENUM (AUTHORITATIVE)
# ============================================================

class DomPipelinePhase(Enum):
    """
    Authoritative DOM pipeline phases.

    Ordering is strict and immutable.
    """

    INITIAL_REVIEW_COMPLETE = "initial_review_complete"
    FILTERED = "filtered"
    SPATIAL_SIGNALS = "spatial_signals"
    CONFIDENCE_ORDERED = "confidence_ordered"
    PROCEDURALLY_RESOLVED = "procedurally_resolved"


# ============================================================
# PIPELINE ENTRYPOINT
# ============================================================

def run_dom_pipeline(
    *,
    post: PostNode,
) -> None:
    """
    Execute the DOM pipeline for a single post.

    Preconditions:
    - DOM tree already exists
    - Gazetteer lookup already performed
    - Initial user review is complete
    - Deselected nodes/candidates are authoritative

    Guarantees:
    - Deterministic execution
    - Append-only persistence
    - No semantic inference
    """

    # --------------------------------------------------------
    # Phase 0 — Initial reviewed snapshot (baseline)
    # --------------------------------------------------------

    persist_dom_snapshot(
        post=post,
        phase=DomPipelinePhase.INITIAL_REVIEW_COMPLETE,
    )

    # --------------------------------------------------------
    # Phase 1 — Hard candidate filtering (Phase 5c)
    # --------------------------------------------------------

    for location in _iter_locations(post):
        filter_location_candidates(location)

    persist_dom_snapshot(
        post=post,
        phase=DomPipelinePhase.FILTERED,
    )

    # --------------------------------------------------------
    # Phase 2 — Spatial signal generation (Phase 5e–5g)
    # --------------------------------------------------------

    compute_spatial_signals(post)

    persist_dom_snapshot(
        post=post,
        phase=DomPipelinePhase.SPATIAL_SIGNALS,
    )

    # --------------------------------------------------------
    # Phase 3 — Candidate confidence aggregation (Phase 5d-A)
    # --------------------------------------------------------

    for location in _iter_locations(post):
        compute_candidate_confidence(location)

    persist_dom_snapshot(
        post=post,
        phase=DomPipelinePhase.CONFIDENCE_ORDERED,
    )

    # --------------------------------------------------------
    # Phase 4 — Procedural resolution (Phase 5d-B)
    # --------------------------------------------------------

    for location in _iter_locations(post):
        resolution = determine_location_resolution(
            confidence_result=location.confidence_result
        )
        location.resolution = resolution

    persist_dom_snapshot(
        post=post,
        phase=DomPipelinePhase.PROCEDURALLY_RESOLVED,
    )


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _iter_locations(post: PostNode) -> Iterable[LocationNode]:
    """
    Yield all selected LocationNodes in the post.

    Deselected nodes are treated as non-existent.
    """
    for section in post.children:
        if not section.selected:
            continue

        for event in section.children:
            if not event.selected:
                continue

            for series in event.children:
                if not series.selected:
                    continue

                for location in series.children:
                    if location.selected:
                        yield location
