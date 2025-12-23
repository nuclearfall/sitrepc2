from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from sitrepc2.dom.nodes import (
    PostNode,
    SectionNode,
    EventNode,
    LocationSeriesNode,
    LocationNode,
    LocationCandidateNode,
    Context,
)


# ============================================================
# REVIEW STAGE
# ============================================================

class ReviewStage(Enum):
    INITIAL = "initial"
    FINAL = "final"


# ============================================================
# REPORT NODE (UNIVERSAL)
# ============================================================

@dataclass(frozen=True)
class ReportNode:
    """
    GUI-agnostic, tree-compatible report node.

    This is a projection of DOM state, not a mutable model.
    """

    node_type: str
    node_id: str
    parent_id: Optional[str]

    summary: str
    selected: bool

    review_stage: ReviewStage
    inspection: Dict[str, Any]

    children: List["ReportNode"]


# ============================================================
# PUBLIC ENTRYPOINTS
# ============================================================

def build_initial_review_report(posts: Iterable[PostNode]) -> List[ReportNode]:
    """
    Build report output for INITIAL REVIEW.

    No confidence
    No resolution states
    Candidates unordered
    """
    return [
        _build_post_report(post, ReviewStage.INITIAL)
        for post in posts
        if post.selected
    ]


def build_final_review_report(posts: Iterable[PostNode]) -> List[ReportNode]:
    """
    Build report output for FINAL REVIEW.

    Confidence visible
    Resolution states visible
    Candidates ordered
    """
    return [
        _build_post_report(post, ReviewStage.FINAL)
        for post in posts
        if post.selected
    ]


# ============================================================
# BUILDERS (POST → LEAVES)
# ============================================================

def _build_post_report(post: PostNode, stage: ReviewStage) -> ReportNode:
    node_id = f"post:{post.ingest_post_id}"

    children = [
        _build_section_report(sec, node_id, stage)
        for sec in post.children
        if sec.selected
    ]

    return ReportNode(
        node_type="POST",
        node_id=node_id,
        parent_id=None,
        summary=f"Post {post.ingest_post_id}",
        selected=post.selected,
        review_stage=stage,
        inspection={
            "ingest_post_id": post.ingest_post_id,
            "pipeline_phase": getattr(post, "pipeline_phase", None),
        },
        children=children,
    )


def _build_section_report(
    section: SectionNode,
    parent_id: str,
    stage: ReviewStage,
) -> ReportNode:
    node_id = f"{parent_id}/section:{section.section_index}"

    children = [
        _build_event_report(evt, node_id, stage)
        for evt in section.children
        if evt.selected
    ]

    return ReportNode(
        node_type="SECTION",
        node_id=node_id,
        parent_id=parent_id,
        summary=f"Section {section.section_index}",
        selected=section.selected,
        review_stage=stage,
        inspection={"section_index": section.section_index},
        children=children,
    )


def _build_event_report(
    event: EventNode,
    parent_id: str,
    stage: ReviewStage,
) -> ReportNode:
    node_id = f"{parent_id}/event:{event.event_uid}"

    children = [
        _build_series_report(series, node_id, stage)
        for series in event.children
        if series.selected
    ]

    return ReportNode(
        node_type="EVENT",
        node_id=node_id,
        parent_id=parent_id,
        summary="Event",
        selected=event.selected,
        review_stage=stage,
        inspection={
            "event_uid": event.event_uid,
            "negated": event.negated,
            "uncertain": event.uncertain,
        },
        children=children,
    )


def _build_series_report(
    series: LocationSeriesNode,
    parent_id: str,
    stage: ReviewStage,
) -> ReportNode:
    node_id = f"{parent_id}/series:{series.series_index}"

    children = [
        _build_location_report(loc, node_id, stage)
        for loc in series.children
        if loc.selected
    ]

    return ReportNode(
        node_type="LOCATION_SERIES",
        node_id=node_id,
        parent_id=parent_id,
        summary="Location series",
        selected=series.selected,
        review_stage=stage,
        inspection={"series_index": series.series_index},
        children=children,
    )


def _build_location_report(
    location: LocationNode,
    parent_id: str,
    stage: ReviewStage,
) -> ReportNode:
    node_id = f"{parent_id}/location:{location.location_index}"

    candidates = list(location.children)

    if stage is ReviewStage.FINAL:
        candidates = sorted(
            candidates,
            key=lambda c: getattr(c, "confidence", 0.0),
            reverse=True,
        )

    children = [
        _build_candidate_report(cand, node_id, stage)
        for cand in candidates
        if cand.selected
    ]

    summary = f"Location: {location.mention_text}"
    if stage is ReviewStage.FINAL:
        summary += f" ({location.resolution_state.value.lower()})"

    return ReportNode(
        node_type="LOCATION",
        node_id=node_id,
        parent_id=parent_id,
        summary=summary,
        selected=location.selected,
        review_stage=stage,
        inspection={
            "mention_text": location.mention_text,
            "resolution_state": getattr(location, "resolution_state", None),
            "confidence": getattr(location, "confidence", None),
        },
        children=children,
    )


def _build_candidate_report(
    cand: LocationCandidateNode,
    parent_id: str,
    stage: ReviewStage,
) -> ReportNode:
    snap = cand.gazetteer_snapshot

    node_id = f"{parent_id}/candidate:{snap['location_id']}"

    summary = (
        f"Candidate: {snap.get('name')}, "
        f"{snap.get('region')} "
        f"({snap.get('lat'):.4f}, {snap.get('lon'):.4f})"
    )

    if stage is ReviewStage.FINAL:
        summary += f" (conf {cand.confidence:.2f})"

    return ReportNode(
        node_type="LOCATION_CANDIDATE",
        node_id=node_id,
        parent_id=parent_id,
        summary=summary,
        selected=cand.selected,
        review_stage=stage,
        inspection={
            "gazetteer_snapshot": snap,
            "confidence": getattr(cand, "confidence", None),
            "rank": getattr(cand, "rank", None),
        },
        children=[],
    )
