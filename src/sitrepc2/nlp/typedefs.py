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
    raw_verb: str     # verb as seen in the original event text


# ---------------------------------------------------------------------------
# Actor Entity
# ---------------------------------------------------------------------------

@dataclass
class Actor:
    """
    Actor involved in an event (unit, group AO, generic force, etc.).
    """
    name: str
    role: str = "primary"
    is_group: bool = False
    is_generic: bool = False


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
    value: Any   # RegionEntry | DirectionEntry | LocaleEntry | string

    # optional scoping
    location_id: Optional[str] = None
    event_id: Optional[str] = None
    section_id: Optional[str] = None
    post_id: Optional[str] = None


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
    Represents a location mention and its full candidate set.
    Used in review and final resolution.
    """
    text: str                           # raw location string from event text
    candidates: List[LocaleCandidate]   # possible matches

    selection: Optional[LocaleCandidate] = None
    selection_confidence: float = 0.0   # equals selection.confidence normally

    cluster_id: Optional[int] = None    # series grouping
    contexts: List[SitRepContext] = field(default_factory=list)


# ---------------------------------------------------------------------------
# War Event Object
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

    negated: bool = False
    uncertain: bool = False
    involves_coreference: bool = False
