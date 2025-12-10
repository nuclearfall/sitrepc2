# src/sitrepc2/review/pd_nodes.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Any

from sitrepc2.events.typedefs import SitRepContext
from sitrepc2.gazetteer.typedefs import LocaleEntry
from sitrepc2.spatial.clustering import ClusterDiagnostics


# ============================================================
# BASE REVIEW NODE CLASS
# ============================================================

@dataclass
class ReviewNode:
    """
    Abstract tree node for pre-/post-DOM review.
    All PD nodes inherit from this.
    """
    parent: Optional["ReviewNode"] = field(default=None, repr=False)
    children: List["ReviewNode"] = field(default_factory=list, repr=False)

    # GUI & display fields
    summary: str = ""
    snippet: str = ""

    # Node-level contexts (from LSS)
    contexts: List[SitRepContext] = field(default_factory=list)

    # Whether this node is *checked in the GUI* (user selected for DOM processing)
    enabled: bool = True

    def add_child(self, node: "ReviewNode") -> None:
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
class PDPost(ReviewNode):
    post_id: str = ""
    raw_text: str = ""


# ============================================================
# SECTION
# ============================================================

@dataclass
class PDSection(ReviewNode):
    section_id: str = ""
    raw_text: str = ""


# ============================================================
# EVENT
# ============================================================

@dataclass
class PDEvent(ReviewNode):
    """
    PDEvent holds:
      - actor
      - action
      - contexts (from LSS)
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
class PDLocation(ReviewNode):
    """
    Represents a single location mention from NLP.
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
