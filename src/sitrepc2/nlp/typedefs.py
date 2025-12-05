from dataclasses import dataclass
from typing import Any, Iterable, Optional

from spacy.tokens import Doc, Span, Token

from sitrepc2.gazetteer.index import GazetteerIndex, LocaleEntry, RegionEntry


class LocationKind(Enum):
    """
    * LOCALE — only locale candidates exist
    * REGION — only a region candidate exists
    * AMBIGUOUS – both exist
    * GENERIC - generic location words like 'town'
    """

    LOCALE = auto()
    REGION = auto()
    AMBIGUOUS = auto()
    GENERIC = auto()

@dataclass
class EventLocationMention:
    event_id: str
    post_id: str

    text: str
    span_start: int          # token index in the Doc
    span_end: int            # exclusive
    sentence_index: int      # optional, for debugging/review

    # Gazeteer candidates (not yet resolved to a single locale or region)
    candidates: list[LocaleEntry|RegionEntry]


@dataclass
class LocaleCandidate:
    entry: LocaleEntry
    distance_loc: float | None                # already used
    # new, optional fields:
    direction_id: str | None = None           # 
    direction_label: str | None = None        # e.g. "Slavyansk"
    dir_along_km: float | None = None         # from axis_metrics_km
    dir_cross_km: float | None = None         # from axis_metrics_km

    def has_direction(self):
        return bool(direction_id)

@dataclass
class WarEvent:
    event_id: str
    post_id: str
    label: str
    text: str
    negated: bool
    uncertain: bool
    involves_coreference: bool
    overall_similarity: float

    holmes_match: HolmesEventMatch
    locations: list["EventLocation"] = field(default_factory=list)

