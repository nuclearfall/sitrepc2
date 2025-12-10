# src/sitrepc2/review/pd_reader.py

from __future__ import annotations
from typing import Dict, Any, List

import json

from sitrepc2.review.pd_nodes import (
    PDPost, PDSection, PDEvent, PDLocation, ReviewNode
)

from sitrepc2.events.typedefs import (
    SitRepContext, CtxKind,
    LocaleCandidate
)

from sitrepc2.gazetteer.typedefs import LocaleEntry
from sitrepc2.util.encoding import decode_coord_u64


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _load_locale_from_dict(d: Dict[str, Any]) -> LocaleEntry:
    """
    PDWriter writes LocaleEntry as a dict. We reconstruct it here.
    """
    return LocaleEntry(
        cid=d["cid"],
        name=d["name"],
        aliases=d.get("aliases", []),
        lon=float(d["lon"]),
        lat=float(d["lat"]),
        region=d.get("region"),
        ru_group=d.get("ru_group"),
        place=d.get("place"),
        wikidata=d.get("wikidata"),
        usage=int(d.get("usage", 0)),
        source=d.get("source", "base"),
    )


def _load_candidate_from_dict(d: Dict[str, Any]) -> LocaleCandidate:
    """
    Reconstruct a LocaleCandidate from JSON.
    """
    locale = _load_locale_from_dict(d["locale"])

    cand = LocaleCandidate(locale=locale, confidence=float(d["confidence"]))

    # Optional metrics
    cand.distance_from_frontline_km = d.get("distance_from_frontline_km")
    cand.distance_from_anchor_km = d.get("distance_from_anchor_km")
    cand.is_cluster_outlier = d.get("is_cluster_outlier")
    cand.scores = d.get("scores", {})

    return cand


def _load_context_from_dict(d: Dict[str, Any]) -> SitRepContext:
    """
    Reconstruct SitRepContext from JSON.
    """
    kind = CtxKind(d["kind"])
    text = d["text"]

    return SitRepContext(
        kind=kind,
        text=text,
        value=None,  # DOM later resolves .value to RegionEntry, LocaleEntry, etc.
        location_id=d.get("location_id"),
        event_id=d.get("event_id"),
        section_id=d.get("section_id"),
        post_id=d.get("post_id"),
    )


# ------------------------------------------------------------
# Node Reconstruction Dispatch
# ------------------------------------------------------------

def _load_pd_location(d: Dict[str, Any], parent: PDEvent | None) -> PDLocation:
    loc = PDLocation(
        location_id=d["location_id"],
        raw_text=d["raw_text"],
        span_text=d.get("span_text"),
        enabled=d.get("enabled", True),
        parent=parent,
    )

    # candidates
    loc.candidates = [_load_candidate_from_dict(c) for c in d.get("candidates", [])]

    # final_locale (optional)
    if "final_locale" in d and d["final_locale"] is not None:
        loc.final_locale = _load_locale_from_dict(d["final_locale"])

    # contexts
    loc.contexts = [_load_context_from_dict(c) for c in d.get("contexts", [])]

    # summary/snippet (optional UI artifacts)
    loc.summary = d.get("summary")
    loc.snippet = d.get("snippet")

    return loc


def _load_pd_event(d: Dict[str, Any], parent: PDSection | None) -> PDEvent:
    ev = PDEvent(
        event_id=d["event_id"],
        raw_text=d["raw_text"],
        enabled=d.get("enabled", True),
        parent=parent,
    )

    # Actor
    ev.actor_kind = d.get("actor_kind")
    ev.actor_text = d.get("actor_text")

    # Action
    ev.action_kind = d.get("action_kind")
    ev.action_text = d.get("action_text")

    # Contexts
    ev.contexts = [_load_context_from_dict(c) for c in d.get("contexts", [])]

    # Children: Locations
    for child_d in d.get("children", []):
        child = _load_pd_location(child_d, ev)
        ev.children.append(child)

    ev.summary = d.get("summary")
    ev.snippet = d.get("snippet")

    return ev


def _load_pd_section(d: Dict[str, Any], parent: PDPost | None) -> PDSection:
    sec = PDSection(
        section_id=d["section_id"],
        raw_text=d["raw_text"],
        enabled=d.get("enabled", True),
        parent=parent,
    )

    sec.contexts = [_load_context_from_dict(c) for c in d.get("contexts", [])]

    # Events
    for child_d in d.get("children", []):
        child = _load_pd_event(child_d, sec)
        sec.children.append(child)

    sec.summary = d.get("summary")
    sec.snippet = d.get("snippet")

    return sec


def _load_pd_post(d: Dict[str, Any], parent=None) -> PDPost:
    post = PDPost(
        post_id=d["post_id"],
        raw_text=d["raw_text"],
        enabled=d.get("enabled", True),
        parent=None,
    )

    post.contexts = [_load_context_from_dict(c) for c in d.get("contexts", [])]

    for child_d in d.get("children", []):
        child = _load_pd_section(child_d, post)
        post.children.append(child)

    post.summary = d.get("summary")
    post.snippet = d.get("snippet")

    return post


# ------------------------------------------------------------
# PUBLIC API
# ------------------------------------------------------------

def load_pd_tree(path: str) -> List[PDPost]:
    """
    Load a PD tree JSON file and reconstruct PDPost → PDSection → PDEvent → PDLocation.
    Returns a list of PDPost objects.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    posts = []
    for post_d in data.get("posts", []):
        posts.append(_load_pd_post(post_d))

    return posts
