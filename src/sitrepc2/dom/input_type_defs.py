from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

from sitrepc2.gazetteer.typedefs import LocaleEntry


# ============================================================
# PIPELINE STAGE
# ============================================================

class PipelineStage(str, Enum):
    LSS = "LSS"
    REVIEW = "REVIEW"
    DOM = "DOM"
    RESOLUTION = "RESOLUTION"
    COMMIT = "COMMIT"


# ============================================================
# CONTEXT
# ============================================================

class ContextKind(str, Enum):
    LOCATION = "location"
    REGION = "region"
    DIRECTION = "direction"
    GROUP = "group"
    PROXIMITY = "proximity"


@dataclass(frozen=True)
class DOMContextInput:
    context_id: str
    kind: ContextKind
    text: str
    scope: str        # POST | SECTION | CLAIM
    source: str       # lss | user


# ============================================================
# LOCATION CANDIDATES (PRE-DOM)
# ============================================================

@dataclass
class DOMLocaleCandidateInput:
    """
    A single gazetteer-backed candidate for a location mention.
    No scoring or filtering has occurred yet.
    """
    locale: LocaleEntry

    # filled later by DOM
    scores: Dict[str, float] = field(default_factory=dict)

    distance_from_frontline_km: Optional[float] = None
    distance_from_anchor_km: Optional[float] = None

    cluster_id: Optional[int] = None
    is_cluster_outlier: Optional[bool] = None

    rejected: bool = False
    rejection_reason: Optional[str] = None


@dataclass
class DOMLocationInput:
    """
    A location mention with a full candidate set.
    """
    location_id: str
    text: str
    asserted: bool

    candidates: List[DOMLocaleCandidateInput]


# ============================================================
# ACTOR / ACTION
# ============================================================

class ActorKindHint(str, Enum):
    UNIT = "unit"
    GROUP = "group"
    GENERIC = "generic"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DOMActorInput:
    actor_id: str
    text: str
    kind_hint: ActorKindHint


@dataclass(frozen=True)
class DOMActionInput:
    action_id: str
    text: str


# ============================================================
# EVENT CLAIM
# ============================================================

@dataclass
class DOMEventClaimInput:
    claim_id: str
    text: str

    negated: bool
    uncertain: bool

    locations: List[DOMLocationInput]
    actors: List[DOMActorInput]
    actions: List[DOMActionInput]
    contexts: List[DOMContextInput]


# ============================================================
# SECTION
# ============================================================

@dataclass
class DOMSectionInput:
    section_id: str
    position: int
    text: str

    contexts: List[DOMContextInput]
    claims: List[DOMEventClaimInput]


# ============================================================
# POST
# ============================================================

@dataclass
class DOMPostInput:
    post_id: str

    source: str
    channel: str
    channel_lang: Optional[str]
    published_at: str
    fetched_at: str

    contexts: List[DOMContextInput]
    sections: List[DOMSectionInput]
