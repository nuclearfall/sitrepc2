from dataclasses import dataclass
from typing import List


@dataclass
class ReviewContext:
    id: str
    kind: str
    text: str
    enabled: bool


@dataclass
class ReviewHint:
    id: str
    text: str
    enabled: bool
    kind: str | None = None


@dataclass
class ReviewClaim:
    claim_id: str
    enabled: bool
    summary: str
    negated: bool
    uncertain: bool
    contexts: List[ReviewContext]
    locations: List[ReviewHint]
    actors: List[ReviewHint]
    actions: List[ReviewHint]


@dataclass
class ReviewSection:
    section_id: str
    enabled: bool
    summary: str
    contexts: List[ReviewContext]
    claims: List[ReviewClaim]


@dataclass
class ReviewPost:
    post_id: str
    enabled: bool
    channel: str
    published_at: str
    contexts: List[ReviewContext]
    sections: List[ReviewSection]
