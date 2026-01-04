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

    Contract:
    - Not a node
    - Selectable
    - Applies downward unless contradicted
    - Deselected context is treated as non-existent
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

    Contract:
    - Metadata only (not a node)
    - May optionally link to gazetteer
    - Selection controls downstream inclusion
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

    Contract:
    - Structure only (no inference, no persistence)
    - Semantics derive from subclass
    - Parent/children define the DOM tree
    - Selection excludes node and all descendants
    """

    # -------- NON-DEFAULT (MUST COME FIRST) --------

    node_id: int
    summary: str

    # -------- DEFAULTS (SAFE FOR INHERITANCE) ------

    selected: bool = True
    parent: Optional["DomNode"] = None
    children: List["DomNode"] = field(default_factory=list)
    contexts: List[Context] = field(default_factory=list)

    # ------------------------------------------------

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
# SECTION NODE (MANDATORY CONSOLIDATION)
# ============================================================

@dataclass(slots=True)
class SectionNode(DomNode):
    """
    Consolidated section node.
    """

    section_index: int


# ============================================================
# EVENT NODE (CORE SEMANTIC UNIT)
# ============================================================

@dataclass(slots=True)
class EventNode(DomNode):
    """
    Core semantic unit of the DOM.
    """

    event_uid: str
    actors: List[Actor] = field(default_factory=list)


# ============================================================
# LOCATION SERIES NODE
# ============================================================

@dataclass(slots=True)
class LocationSeriesNode(DomNode):
    """
    Groups one or more location mentions for an event.
    """

    series_index: int


# ============================================================
# LOCATION NODE
# ============================================================

@dataclass(slots=True)
class LocationNode(DomNode):
    """
    A single location mention.
    """

    mention_text: str
    resolved: bool = False


# ============================================================
# LOCATION CANDIDATE NODE (EMBEDDED SNAPSHOT)
# ============================================================

@dataclass(slots=True)
class LocationCandidateNode(DomNode):
    """
    Snapshot of a gazetteer location (or manual entry).

    Contract:
    - Self-contained historical snapshot
    - Does not depend on live gazetteer state
    - Does not embed derived relationships
    """

    # -------- Provenance --------

    gazetteer_location_id: Optional[int]

    # -------- Embedded gazetteer snapshot --------

    lat: Optional[float]
    lon: Optional[float]
    name: Optional[str]
    place: Optional[str]
    wikidata: Optional[str]

    # -------- Review metadata --------

    confidence: Optional[float]
    persists: bool
    dist_from_front: float
