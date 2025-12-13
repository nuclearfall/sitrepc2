from review.db import connect
from review.models import *


def load_posts() -> list[ReviewPost]:
    with connect() as con:
        rows = con.execute(
            "SELECT post_id, channel, published_at, enabled FROM posts"
        ).fetchall()

    return [load_post(r[0]) for r in rows]


def load_post(post_id: str) -> ReviewPost:
    with connect() as con:
        post = con.execute(
            "SELECT post_id, channel, published_at, enabled FROM posts WHERE post_id=?",
            (post_id,),
        ).fetchone()

        contexts = _load_contexts(con, "POST", post_id=post_id)
        sections = _load_sections(con, post_id)

    return ReviewPost(
        post_id=post[0],
        channel=post[1],
        published_at=post[2],
        enabled=bool(post[3]),
        contexts=contexts,
        sections=sections,
    )


def _load_sections(con, post_id: str) -> list[ReviewSection]:
    rows = con.execute(
        """
        SELECT section_id, enabled, substr(text,1,120)
        FROM sections
        WHERE post_id=?
        ORDER BY position
        """,
        (post_id,),
    ).fetchall()

    return [
        ReviewSection(
            section_id=r[0],
            enabled=bool(r[1]),
            summary=r[2],
            contexts=_load_contexts(con, "SECTION", section_id=r[0]),
            claims=_load_claims(con, r[0]),
        )
        for r in rows
    ]


def _load_claims(con, section_id: str) -> list[ReviewClaim]:
    rows = con.execute(
        """
        SELECT claim_id, enabled, substr(text,1,160), negated, uncertain
        FROM event_claims
        WHERE section_id=?
        """,
        (section_id,),
    ).fetchall()

    return [
        ReviewClaim(
            claim_id=r[0],
            enabled=bool(r[1]),
            summary=r[2],
            negated=bool(r[3]),
            uncertain=bool(r[4]),
            contexts=_load_contexts(con, "CLAIM", claim_id=r[0]),
            locations=_load_hints(con, "location_hints", "location_hint_id", r[0]),
            actors=_load_hints(con, "actor_hints", "actor_hint_id", r[0], kind=True),
            actions=_load_hints(con, "action_hints", "action_hint_id", r[0]),
        )
        for r in rows
    ]


def _load_contexts(con, scope, **ids):
    q = "SELECT context_id, kind, text, enabled FROM context_hints WHERE scope=?"
    params = [scope]
    for k, v in ids.items():
        q += f" AND {k}=?"
        params.append(v)

    rows = con.execute(q, params).fetchall()
    return [ReviewContext(*r) for r in rows]


def _load_hints(con, table, idcol, claim_id, kind=False):
    cols = f"{idcol}, text, enabled" + (", kind_hint" if kind else "")
    rows = con.execute(
        f"SELECT {cols} FROM {table} WHERE claim_id=?",
        (claim_id,),
    ).fetchall()

    return [
        ReviewHint(
            id=r[0],
            text=r[1],
            enabled=bool(r[2]),
            kind=r[3] if kind else None,
        )
        for r in rows
    ]
