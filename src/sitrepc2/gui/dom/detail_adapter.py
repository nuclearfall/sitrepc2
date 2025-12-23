from __future__ import annotations

from typing import Any, Dict, List, Optional

from sitrepc2.dom.dom_report import ReportNode


# ============================================================
# DETAIL PAYLOAD CONTRACT
# ============================================================

DetailPayload = Dict[str, Any]


# ============================================================
# PUBLIC API
# ============================================================

def build_detail_payload(node: ReportNode) -> DetailPayload:
    """
    Convert a ReportNode into a UI-agnostic inspection payload.

    This function:
    - does NOT mutate node
    - does NOT infer state
    - does NOT apply defaults
    - reflects exactly what DOM decided
    """

    payload: DetailPayload = {
        "node_type": node.node_type,
        "node_id": node.node_id,
        "summary": node.summary,
        "selected": node.selected,
        "review_stage": node.review_stage,
        "inspection": {},
    }

    insp = node.inspection or {}

    # --------------------------------------------------------
    # Common inspection fields
    # --------------------------------------------------------

    payload["inspection"]["text"] = insp.get("text")
    payload["inspection"]["resolution_state"] = insp.get("resolution_state")
    payload["inspection"]["confidence"] = insp.get("confidence")

    # --------------------------------------------------------
    # Context (always inspectable, never nodes)
    # --------------------------------------------------------

    contexts = insp.get("contexts", [])
    payload["inspection"]["contexts"] = [
        {
            "kind": ctx.get("kind"),
            "text": ctx.get("text"),
            "scope": ctx.get("scope"),
        }
        for ctx in contexts
    ]

    # --------------------------------------------------------
    # Location-specific inspection
    # --------------------------------------------------------

    if node.node_type == "LOCATION":
        payload["inspection"]["mention_text"] = insp.get("mention_text")
        payload["inspection"]["resolved"] = insp.get("resolved", False)

    # --------------------------------------------------------
    # Candidate inspection
    # --------------------------------------------------------

    candidates = insp.get("candidates")
    if candidates is not None:
        payload["inspection"]["candidates"] = [
            _candidate_payload(c)
            for c in candidates
        ]

    return payload


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _candidate_payload(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a LocationCandidateNode snapshot for inspection.
    """

    return {
        "location_id": candidate.get("location_id"),
        "name": candidate.get("name"),
        "region": candidate.get("region"),
        "group": candidate.get("group"),
        "lat": candidate.get("lat"),
        "lon": candidate.get("lon"),
        "confidence": candidate.get("confidence"),
        "resolved": candidate.get("resolved", False),
    }
