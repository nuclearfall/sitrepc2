# src/sitrepc2/review/pd_nodes.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Any

from sitrepc2.gazetteer.typedefs import LocaleEntry, GroupEntry, RegionEntry, DirectionEntry
from sitrepc2.spatial.clustering import ClusterDiagnostics

class ContextKind(Enum):
    LOCATION = "LOCATION"
    REGION: "REGION"
    DIRECTION: "DIRECTION"
    GROUP: "GROUP"

@dataclass
class Context:
    ctx_id: str
    # kind is passed from spaCy to Holmes. Each string value corresponds to 
    # the label of an entity ruler.
    ctx_kind: ContextKind
    text: str = ""


    enabled: bool = True


# ============================================================
# BASE REVIEW NODE CLASS
# ============================================================

@dataclass
class Node:
    """
    Abstract tree node. All nodes inherit from this. Nodes should be enriched
    at each stage and should be easily slotted into a CLUI/GUI.
    """
    # Node-level ctxs.
    ctxs: List[Context] = field(default_factory=list)

    parent: Optional["Node"] = field(default=None, repr=False)
    children: Optional[List["Node"]] = field(default_factory=list, repr=False)

    # GUI & display fields
    summary: str = ""
    snippet: str = ""

    # Whether this node is *checked in the GUI* (user selected for DOM processing)
    enabled: bool = True


    def add_child(self, node: "Node") -> None:
        node.parent = self
        self.children.append(node)

    def iter_descendants(self):
        for c in self.children:
            yield c
            yield from c.iter_descendants()


# ============================================================
# POST
# ============================================================

@dataclass
class Post(Node):
    post_id: str = ""
    raw_text: str = ""


# ============================================================
# SECTION
# ============================================================

@dataclass
class Section(Node):
    section_id: str = ""
    raw_text: str = ""


# ============================================================
# EVENT
# ============================================================

@dataclass
class Event(Node):
    """
    PDEvent holds:
      - actor
      - action
      - ctxs (from LSS)
      - cluster diagnostics added during DOM
    """
    event_id: str = ""
    raw_text: str = ""

    # Actor resolution (from LSS)
    actor_kind: Optional[str] = None
    actor_text: Optional[str] = None

    # Action resolution (from LSS)
    action_kind: Optional[str] = None
    action_text: Optional[str] = None

    # DOM output
    cluster_diagnostics: Optional[ClusterDiagnostics] = None


# ============================================================
# LOCATION
# ============================================================

@dataclass
class Location(Node):
    """
    Represents a single location mention from LSS. Locations
    are 
    Has:
      - raw span text
      - LSS-derived candidates
      - final locale & confidence (set by DOM)
    """
    location_id: str = ""
    raw_text: str = ""
    span_text: str = ""

    # List[LocaleCandidate] from LSS
    candidates: List[Any] = field(default_factory=list)

    # Convenience list for UI summaries
    candidate_texts: List[str] = field(default_factory=list)

    # DOM layer outputs
    final_locale: Optional[LocaleEntry] = None
    final_confidence: Optional[float] = None

    # Optional: direction or proximity anchor used
    resolved_anchor: Optional[LocaleEntry] = None
