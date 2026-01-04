from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Literal


# ============================================================
# CONTEXT (METADATA, NOT A NODE)
# ============================================================

@dataclass(frozen=True, slots=True)
class Context:
    """
    Contextual constraint applied to a node.
    """

    ctx_kind: Literal["REGION", "GROUP", "DIRECTION"]
    value: str
    selected: bool = True


# ============================================================
# ACTOR (METADATA, NOT A NODE)
# ============================================================

@dataclass(frozen=True, slots=True)
class Actor:
    """
    Actor extracted from LSS / Holmes.
    """

    text: str
    gazetteer_group_id: Optional[int]
    selected: bool = True


# ============================================================
# BASE DOM NODE (STRUCTURAL ONLY)
# ============================================================

@dataclass(slots=True)
class DomNode:
    """
    Base class for all DOM tree nodes.

    NOTE:
    Only immutable structural identity belongs in __init__.
    Mutable state is attached post-construction.
    """

    # -------- STRUCTURAL IDENTITY (NO DEFAULTS) --------

    node_id: str
    summary: str

    # -------- MUTABLE STATE (NOT IN __init__) --------

    selected: bool = field(default=True, init=False)
    parent: Optional["DomNode"] = field(default=None, init=False)
    children: List["DomNode"] = field(default_factory=list, init=False)
    contexts: List[Context] = field(default_factory=list, init=False)

    # --------------------------------------------------

    def add_child(self, child: "DomNode") -> None:
        child.parent = self
        self.children.append(child)


# ============================================================
# POST NODE (ROOT)
# ============================================================

@dataclass(slots=True)
class PostNode(DomNode):
    """
    Root node for a single ingest post.
    """

    ingest_post_id: int
    lss_run_id: int


# ============================================================
# SECTION NODE
# ============================================================

@dataclass(slots=True)
class SectionNode(DomNode):
    section_index: int


# ============================================================
# EVENT NODE
# ============================================================

@dataclass(slots=True)
class EventNode(DomNode):
    event_uid: str
    actors: List[Actor] = field(default_factory=list)


# ============================================================
# LOCATION SERIES NODE
# ============================================================

@dataclass(slots=True)
class LocationSeriesNode(DomNode):
    series_index: int


# ============================================================
# LOCATION NODE
# ============================================================

@dataclass(slots=True)
class LocationNode(DomNode):
    mention_text: str
    resolved: bool = False


# ============================================================
# LOCATION CANDIDATE NODE
# ============================================================

@dataclass(slots=True)
class LocationCandidateNode(DomNode):
    gazetteer_location_id: Optional[int]

    lat: Optional[float]
    lon: Optional[float]
    name: Optional[str]
    place: Optional[str]
    wikidata: Optional[str]

    confidence: Optional[float]
    persists: bool
    dist_from_front: float
