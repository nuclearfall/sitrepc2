# src/sitrepc2/nlp/typedefs.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Union, Dict, Any

if TYPE_CHECKING:
    from gazetteer.typedefs.import LocaleEntry, RegionEntry, OpGroupEntry, DirectionEntry


# ---------------------------------------------------------------------------
# Action Taxonomy
# ---------------------------------------------------------------------------

class ActionKind(Enum):
    SHELLING = "shelling"
    ATTACK = "attack"
    ADVANCE = "advance"
    DEFENSE = "defense"
    CAPTURE = "capture"
    WITHDRAWAL = "withdrawal"
    OTHER = "other"

@dataclass
class Action:
    """
    Normalized action classification.
    """
    kind: ActionKind
    label: str        # taxonomy label, e.g., "artillery_shelling"
    text: str     # verb as seen in the original event text


# ---------------------------------------------------------------------------
# Actor Entity
# ---------------------------------------------------------------------------
class ActorKind(Enum):
    UNIT = "unit"
    GROUP = "group"
    CIVLIAN = "civilian"
    GENERIC = "generic"

@dataclass
class Actor:
    """
    Actor involved in an event (unit, group AO, generic force, etc.).
    """
    kind: ActorKind
    text: str
    role: str = "primary"

# ---------------------------------------------------------------------------
# Context Types
# ---------------------------------------------------------------------------

class CtxKind(Enum):
    REGION = "region"
    DIRECTION = "direction"
    PROXIMITY = "proximity"
    GROUP = "group"


@dataclass
class SitRepContext:
    """
    A contextual hint affecting interpretation of locations/events.
    Scope identifies the level at which it applies.
    """
    kind: CtxKind
    value: Any   # RegionEntry | DirectionEntry | LocaleEntry
    text: str
    # optional scoping
    location_id: Optional[str] = None
    event_id: Optional[str] = None
    section_id: Optional[str] = None
    post_id: Optional[str] = None
    # new mistmatch flag to alert users when context has eliminated all possible candidates
    is_mismatch: Optional[bool] = False
    # NEW: directional / proximity anchor resolution
    anchor: Optional[LocaleEntry] = None
    anchor_candidates: List[LocaleEntry] = field(default_factory=list)

@dataclass
class AnchorCandidate:
    locale: LocaleEntry
    confidence: float = 0.0
    scores: dict = field(default_factory=dict)

@dataclass
class Anchor:
    """
    A reference point required for contextualization.
    Examples:
        - direction anchor ("in the Avdiivka direction")
        - proximity anchor ("near Krasnohorivka")
    """
    text: str                         # raw anchor text
    candidates: List[AnchorCandidate] = field(default_factory=list)

    selection: Optional[AnchorCandidate] = None
    selection_confidence: float = 0.0

    mismatch_detected: bool = False


# ---------------------------------------------------------------------------
# Location Resolution Objects
# ---------------------------------------------------------------------------

@dataclass
class LocaleCandidate:
    """
    A possible resolution for a location string.
    Persists through entire workflow for review.
    """
    locale: LocaleEntry
    confidence: float  # 0.0 - 1.0 probability

    # unary contextual metrics
    distance_from_frontline_km: Optional[float] = None
    distance_from_anchor_km: Optional[float] = None
    is_cluster_outlier: Optional[bool] = None

    # scoring metadata
    scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class Location:
    """
    Represents a location post-nls mention and its full candidate set.
    Used in review and final resolution.
    """
    text: str                           # raw location string from event text
    candidates: List[LocaleCandidate]   # possible matches

    selection: Optional[LocaleCandidate] = None
    selection_confidence: float = 0.0   # equals selection.confidence normally

    cluster_id: Optional[int] = None    # series grouping
    contexts: List[SitRepContext] = field(default_factory=list)
    span: Optional[Tuple[int, int]] = None


# ---------------------------------------------------------------------------
# Event Object
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """
    Canonical war-event object.
    Stable across ingestion → processing → review → commit.
    """
    event_id: str
    post_id: str

    text: str
    actor: Optional[Actor]
    action: Optional[Action]

    locations: List[Location] = field(default_factory=list)
    contexts: List[SitRepContext] = field(default_factory=list)


@dataclass
class Section:
    """
    A logical subdivision of a Post.
    Most Telegram war reports use visible or implicit sectioning to discuss
    different directions, axes, regions, or operational zones.

    Each Section:
        • has section-level context extracted from LSS
        • contains a sequence of Events that appear in it
        • inherits Post-level context, but may override it
    """
    section_id: str
    text: str
    contexts: List[SitRepContext] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)

@dataclass
class Post:
    """
    Represents a single Telegram post after ingestion.

    Holds:
        - raw metadata
        - raw text
        - post-level contexts (from LSS)
        - extracted events (filled in later by pipeline)
    """
    source: str
    channel: str
    channel_lang: str
    post_id: str
    published_at: str
    fetched_at: str
    text: str

    contexts: List[SitRepContext] = field(default_factory=list)  # post-level
    sections: List[Section] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)  # optional flat list
