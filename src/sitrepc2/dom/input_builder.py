# src/sitrepc2/dom/input_builder.py

from __future__ import annotations
import sqlite3
from typing import List, Dict

from sitrepc2.config.paths import get_lss_db_path
from sitrepc2.dom.input_typedefs import (
    DOMPostInput,
    DOMSectionInput,
    DOMEventClaimInput,
    DOMLocationInput,
    DOMContextInput,
)
from sitrepc2.events.typedefs import CtxKind


# ---------------------------------------------------------------------
# DB Connection
# ---------------------------------------------------------------------

def _conn():
    return sqlite3.connect(get_lss_db_path())


# ---------------------------------------------------------------------
# Context Rehydration
# ---------------------------------------------------------------------

def _load_contexts(
    *,
    post_id: str | None = None,
    section_id: str | None = None,
    claim_id: str | None = None,
    location_id: str | None = None,
) -> List[DOMContextInput]:
    """
    Load contexts scoped to the specified entity.
    """
    where = []
    params = []

    if post_id is not None:
        where.append("post_id = ?")
        params.append(post_id)
    if section_id is not None:
        where.append("section_id = ?")
        params.append(section_id)
    if claim_id is not None:
        where.append("claim_id = ?")
        params.append(claim_id)
    if location_id is not None:
        where.append("location_id = ?")
        params.append(location_id)

    clause = " AND ".join(where)

    with _conn() as con:
        rows = con.execute(
            f"""
            SELECT kind, text
            FROM context_hints
            WHERE enabled = 1
              AND {clause}
            """,
            params,
        ).fetchall()

    return [
        DOMContextInput(
            kind=CtxKind(row["kind"]),
            text=row["text"],
        )
        for row in rows
    ]


# ---------------------------------------------------------------------
# Location Rehydration
# ---------------------------------------------------------------------

def _load_locations(claim_id: str) -> List[DOMLocationInput]:
    """
    Load all locations belonging to a claim.
    """
    with _conn() as con:
        rows = con.execute(
            """
            SELECT location_hint_id, text
            FROM location_hints
            WHERE claim_id = ?
              AND enabled = 1
            """,
            (claim_id,),
        ).fetchall()

    locations: List[DOMLocationInput] = []

    for row in rows:
        location_id = row["location_hint_id"]
        locations.append(
            DOMLocationInput(
                location_id=location_id,
                text=row["text"],
                contexts=_load_contexts(location_id=location_id),
            )
        )

    return locations


# ---------------------------------------------------------------------
# Event Claim Rehydration
# ---------------------------------------------------------------------

def _load_event_claims(section_id: str) -> List[DOMEventClaimInput]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT claim_id, text, negated, uncertain
            FROM event_claims
            WHERE section_id = ?
              AND enabled = 1
            """,
            (section_id,),
        ).fetchall()

    claims: List[DOMEventClaimInput] = []

    for row in rows:
        claim_id = row["claim_id"]
        claims.append(
            DOMEventClaimInput(
                claim_id=claim_id,
                text=row["text"],
                negated=bool(row["negated"]),
                uncertain=bool(row["uncertain"]),
                contexts=_load_contexts(
                    claim_id=claim_id,
                    section_id=section_id,
                ),
                locations=_load_locations(claim_id),
            )
        )

    return claims


# ---------------------------------------------------------------------
# Section Rehydration
# ---------------------------------------------------------------------

def _load_sections(post_id: str) -> List[DOMSectionInput]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT section_id, text
            FROM sections
            WHERE post_id = ?
              AND enabled = 1
            ORDER BY position ASC
            """,
            (post_id,),
        ).fetchall()

    sections: List[DOMSectionInput] = []

    for row in rows:
        section_id = row["section_id"]
        sections.append(
            DOMSectionInput(
                section_id=section_id,
                text=row["text"],
                contexts=_load_contexts(
                    post_id=post_id,
                    section_id=section_id,
                ),
                claims=_load_event_claims(section_id),
            )
        )

    return sections


# ---------------------------------------------------------------------
# Post Rehydration (PUBLIC ENTRY POINT)
# ---------------------------------------------------------------------

def load_dom_posts() -> List[DOMPostInput]:
    """
    Load all DOMPostInput objects from the database.
    """
    with _conn() as con:
        rows = con.execute(
            """
            SELECT post_id, source, channel, published_at
            FROM posts
            WHERE enabled = 1
            ORDER BY published_at ASC
            """
        ).fetchall()

    posts: List[DOMPostInput] = []

    for row in rows:
        post_id = row["post_id"]
        posts.append(
            DOMPostInput(
                post_id=post_id,
                source=row["source"],
                channel=row["channel"],
                published_at=row["published_at"],
                contexts=_load_contexts(post_id=post_id),
                sections=_load_sections(post_id),
            )
        )

    return posts
