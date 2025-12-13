from __future__ import annotations
import sqlite3
from typing import List, Dict

from sitrepc2.config.paths import get_lss_db_path
from sitrepc2.dom.input_typedefs import (
    DOMPostInput,
    DOMSectionInput,
    DOMEventClaimInput,
    DOMLocationHintInput,
    DOMActorHintInput,
    DOMActionHintInput,
    DOMContextInput,
    ContextKind,
)


# ------------------------------------------------------------
# DB CONNECTION
# ------------------------------------------------------------

def _conn():
    return sqlite3.connect(get_lss_db_path())


# ------------------------------------------------------------
# PUBLIC ENTRY POINT
# ------------------------------------------------------------

def load_dom_inputs() -> List[DOMPostInput]:
    """
    Load all REVIEW-stage, enabled posts and rebuild DOM input trees.
    """
    with _conn() as con:
        con.row_factory = sqlite3.Row

        posts = _load_posts(con)
        sections = _load_sections(con)
        claims = _load_claims(con)
        contexts = _load_contexts(con)
        locations = _load_locations(con)
        actors = _load_actors(con)
        actions = _load_actions(con)

    # --------------------------
    # Build index maps
    # --------------------------

    sections_by_post: Dict[str, List[DOMSectionInput]] = {}
    claims_by_section: Dict[str, List[DOMEventClaimInput]] = {}

    contexts_by_scope: Dict[str, List[DOMContextInput]] = {}
    locations_by_claim: Dict[str, List[DOMLocationHintInput]] = {}
    actors_by_claim: Dict[str, List[DOMActorHintInput]] = {}
    actions_by_claim: Dict[str, List[DOMActionHintInput]] = {}

    for ctx in contexts:
        contexts_by_scope.setdefault(ctx.scope, []).append(ctx)

    for loc in locations:
        locations_by_claim.setdefault(loc.location_hint_id.split(":")[1], []).append(loc)

    for act in actors:
        actors_by_claim.setdefault(act.actor_hint_id.split(":")[1], []).append(act)

    for act in actions:
        actions_by_claim.setdefault(act.action_hint_id.split(":")[1], []).append(act)

    # --------------------------
    # Attach claims to sections
    # --------------------------

    for claim in claims:
        claim.locations = locations_by_claim.get(claim.claim_id, [])
        claim.actors = actors_by_claim.get(claim.claim_id, [])
        claim.actions = actions_by_claim.get(claim.claim_id, [])
        claim.contexts = [
            c for c in contexts_by_scope.get("CLAIM", [])
            if c.scope == "CLAIM" and c.text
        ]

        claims_by_section.setdefault(claim.claim_id.split(":")[0], []).append(claim)

    # --------------------------
    # Attach sections to posts
    # --------------------------

    for section in sections:
        section.claims = claims_by_section.get(section.section_id, [])
        section.contexts = [
            c for c in contexts_by_scope.get("SECTION", [])
            if c.scope == "SECTION"
        ]

        sections_by_post.setdefault(section.section_id.split(":")[0], []).append(section)

    # --------------------------
    # Final post assembly
    # --------------------------

    out: List[DOMPostInput] = []

    for post in posts:
        post.sections = sections_by_post.get(post.post_id, [])
        post.contexts = [
            c for c in contexts_by_scope.get("POST", [])
            if c.scope == "POST"
        ]
        out.append(post)

    return out


# ------------------------------------------------------------
# LOADERS
# ------------------------------------------------------------

def _load_posts(con) -> List[DOMPostInput]:
    rows = con.execute(
        """
        SELECT * FROM posts
        WHERE enabled = 1 AND stage = 'REVIEW'
        """
    ).fetchall()

    return [
        DOMPostInput(
            post_id=r["post_id"],
            source=r["source"],
            channel=r["channel"],
            channel_lang=r["channel_lang"],
            published_at=r["published_at"],
            fetched_at=r["fetched_at"],
            contexts=[],
            sections=[],
        )
        for r in rows
    ]


def _load_sections(con) -> List[DOMSectionInput]:
    rows = con.execute(
        """
        SELECT * FROM sections
        WHERE enabled = 1 AND stage = 'REVIEW'
        ORDER BY position ASC
        """
    ).fetchall()

    return [
        DOMSectionInput(
            section_id=r["section_id"],
            position=r["position"],
            text=r["text"],
            contexts=[],
            claims=[],
        )
        for r in rows
    ]


def _load_claims(con) -> List[DOMEventClaimInput]:
    rows = con.execute(
        """
        SELECT * FROM event_claims
        WHERE enabled = 1 AND stage = 'REVIEW'
        """
    ).fetchall()

    return [
        DOMEventClaimInput(
            claim_id=r["claim_id"],
            text=r["text"],
            negated=bool(r["negated"]),
            uncertain=bool(r["uncertain"]),
        )
        for r in rows
    ]


def _load_contexts(con) -> List[DOMContextInput]:
    rows = con.execute(
        """
        SELECT * FROM context_hints
        WHERE enabled = 1 AND stage = 'REVIEW'
        """
    ).fetchall()

    return [
        DOMContextInput(
            context_id=r["context_id"],
            kind=ContextKind(r["kind"]),
            text=r["text"],
            scope=r["scope"],
            source=r["source"],
        )
        for r in rows
    ]


def _load_locations(con) -> List[DOMLocationHintInput]:
    rows = con.execute(
        """
        SELECT * FROM location_hints
        WHERE enabled = 1 AND stage = 'REVIEW'
        """
    ).fetchall()

    return [
        DOMLocationHintInput(
            location_hint_id=r["location_hint_id"],
            text=r["text"],
            asserted=bool(r["asserted"]),
        )
        for r in rows
    ]


def _load_actors(con) -> List[DOMActorHintInput]:
    rows = con.execute(
        """
        SELECT * FROM actor_hints
        WHERE enabled = 1 AND stage = 'REVIEW'
        """
    ).fetchall()

    return [
        DOMActorHintInput(
            actor_hint_id=r["actor_hint_id"],
            text=r["text"],
            kind_hint=r["kind_hint"],
        )
        for r in rows
    ]


def _load_actions(con) -> List[DOMActionHintInput]:
    rows = con.execute(
        """
        SELECT * FROM action_hints
        WHERE enabled = 1 AND stage = 'REVIEW'
        """
    ).fetchall()

    return [
        DOMActionHintInput(
            action_hint_id=r["action_hint_id"],
            text=r["text"],
        )
        for r in rows
    ]
