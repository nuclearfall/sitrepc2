from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List

from sitrepc2.gazetteer.index import GazetteerIndex
from sitrepc2.lss.typedefs import Context, CtxKind


@dataclass
class AnchorCandidate:
    cid: int
    locale: object  # LocaleEntry
    score: float = 1.0


@dataclass
class ResolvedAnchor:
    """
    Result used by the DOM pipeline:
      - candidates (one or many)
      - chosen (None until user resolution)
      - mismatched flag
    """
    ctx: Context
    candidates: List[AnchorCandidate]
    chosen: Optional[AnchorCandidate] = None
    mismatch: bool = False


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def resolve_anchors_for_post_tree(post, gaz: GazetteerIndex):
    """
    Scans post → sections → events and resolves all anchors for
    DIRECTION and PROXIMITY contexts.

    Stores results in post.anchor_resolutions: List[ResolvedAnchor]
    """
    resolved: List[ResolvedAnchor] = []

    for section in post.sections:
        for event in section.events:
            for ctx in event.context:

                if ctx.kind not in (CtxKind.DIRECTION, CtxKind.PROXIMITY):
                    continue

                ra = _resolve_single_anchor(ctx, gaz)
                if ra:
                    resolved.append(ra)

    post.anchor_resolutions = resolved
    return resolved


# ---------------------------------------------------------------------------
# INTERNAL LOGIC
# ---------------------------------------------------------------------------

def _resolve_single_anchor(ctx: Context, gaz: GazetteerIndex) -> Optional[ResolvedAnchor]:
    """
    Resolve one directional/proximity anchor.
    """
    txt = ctx.text

    # 1) Try direction lookup
    d = gaz.search_direction(txt)
    if d:
        anchor = gaz._locale_by_cid.get(d.anchor)
        if anchor is None:
            # stale or missing CID
            return ResolvedAnchor(ctx, [], None, mismatch=True)

        cand = AnchorCandidate(cid=d.anchor, locale=anchor, score=1.0)
        return ResolvedAnchor(ctx=ctx, candidates=[cand])

    # 2) Fallback: treat text as locale name
    locs = gaz.search_locale(txt)

    if not locs:
        # unrecognized anchor
        return ResolvedAnchor(ctx, [], None, mismatch=True)

    cands = [
        AnchorCandidate(cid=loc.cid, locale=loc, score=0.7)
        for loc in locs
    ]

    # if exactly one → auto-trust
    if len(cands) == 1:
        cands[0].score = 1.0

    return ResolvedAnchor(ctx=ctx, candidates=cands)
