# src/sitrepc2/lss/summarize.py

from __future__ import annotations
import sqlite3

from sitrepc2.config.paths import get_lss_db_path

def summarize_post(post_id: str) -> dict:
    with sqlite3.connect(get_lss_db_path()) as con:
        cur = con.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM sections WHERE post_id=? AND enabled=1",
            (post_id,),
        )
        section_count = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*) FROM event_claims
            WHERE post_id=? AND enabled=1
            """,
            (post_id,),
        )
        claim_count = cur.fetchone()[0]

        return {
            "post_id": post_id,
            "sections": section_count,
            "claims": claim_count,
        }


def summarize_claim(claim_id: str) -> dict:
    with sqlite3.connect(get_lss_db_path()) as con:
        cur = con.cursor()

        cur.execute(
            "SELECT text, negated, uncertain FROM event_claims WHERE claim_id=?",
            (claim_id,),
        )
        text, neg, unc = cur.fetchone()

        cur.execute(
            "SELECT COUNT(*) FROM location_hints WHERE claim_id=? AND enabled=1",
            (claim_id,),
        )
        locs = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM actor_hints WHERE claim_id=? AND enabled=1",
            (claim_id,),
        )
        actors = cur.fetchone()[0]

        return {
            "claim_id": claim_id,
            "summary": text[:120] + ("…" if len(text) > 120 else ""),
            "negated": neg,
            "uncertain": unc,
            "locations": locs,
            "actors": actors,
        }
