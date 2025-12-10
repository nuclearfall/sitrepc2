# src/sitrepc2/review/pd_summary.py

from __future__ import annotations
from typing import Optional, List, Dict

from sitrepc2.review.pd_nodes import (
    PDPost, PDSection, PDEvent, PDLocation, ReviewNode
)
from sitrepc2.events.typedefs import SitRepContext, CtxKind


# ================================================================
# helper utilities
# ================================================================

def _first_n_chars(text: str, n: int = 300) -> str:
    """Return up to N chars, trimmed and flattened."""
    if not text:
        return ""
    t = text.strip().replace("\n", " ")
    return t[:n] + ("…" if len(t) > n else "")


# ----------------------------------------------------------------
# Anchor resolution tag helper
# ----------------------------------------------------------------

def _anchor_tag_for(ctx: SitRepContext, anchor_info: Dict[SitRepContext, object]) -> str:
    """
    Generate a compact GUI-friendly visual tag for anchor resolution.

    ✓  — resolved unambiguously
    ~  — multiple candidates but not ambiguous enough to reject
    ?  — unresolved or mismatch
    """

    ra = anchor_info.get(ctx)
    if ra is None:
        return ""  # no anchor involvement

    # ra fields expected: candidates, mismatch
    if getattr(ra, "mismatch", False):
        return " (?)"

    cands = getattr(ra, "candidates", None)
    if not cands:
        return " (?)"

    if len(cands) == 1:
        return " ✓"

    return " (~)"


def _ctx_label(ctxs: List[SitRepContext],
               anchor_info: Dict[SitRepContext, object] | None = None) -> str:
    """
    GUI-friendly version of context label generation.
    Example output:
        [Region: Donetsk; Direction: Kupyansk ✓; Group: Vostok]
    """
    if not ctxs:
        return ""

    parts = []
    for ctx in ctxs:
        base = f"{ctx.kind.value.capitalize()}: {ctx.text}"

        if anchor_info:
            base += _anchor_tag_for(ctx, anchor_info)

        parts.append(base)

    return "[" + "; ".join(parts) + "]"


# ================================================================
# Summarizers for each PD node type
# ================================================================

def summarize_post(post: PDPost) -> None:
    """Post-level summarization for GUI tree/list display."""
    post.snippet = _first_n_chars(post.raw_text, 1000)

    anchor_info = {
        ra.ctx: ra for ra in getattr(post, "anchor_resolutions", [])
    }

    ctx_label = _ctx_label(post.contexts, anchor_info)

    # GUI: posts often shown in QListView as top-level entries
    post.summary = f"Post {post.post_id} {ctx_label}".strip()


def summarize_section(section: PDSection) -> None:
    """Section summary, short and GUI-friendly."""
    section.snippet = _first_n_chars(section.raw_text, 300)

    # Sections rarely have anchor contexts, but keep consistent interface
    anchor_info = {
        ra.ctx: ra for ra in getattr(section, "anchor_resolutions", [])
    }

    ctx_label = _ctx_label(section.contexts, anchor_info)
    section.summary = f"Section {section.section_id} {ctx_label}".strip()


def summarize_event(event: PDEvent) -> None:
    """Event summary showing actor/action + context in a compact GUI manner."""
    event.snippet = _first_n_chars(event.raw_text, 250)

    # actor/action
    actor_str = ""
    if event.actor_kind or event.actor_text:
        actor_str = f"{event.actor_kind or ''}:{event.actor_text or ''}".strip(":")

    action_str = ""
    if event.action_kind or event.action_text:
        action_str = f"{event.action_kind or ''}:{event.action_text or ''}".strip(":")

    core = " | ".join(s for s in (actor_str, action_str) if s)

    anchor_info = {
        ra.ctx: ra for ra in getattr(event, "anchor_resolutions", [])
    }

    ctx_label = _ctx_label(event.contexts, anchor_info)

    event.summary = f"{core} {ctx_label}".strip()


def summarize_location(loc: PDLocation) -> None:
    """Location-level summary for GUI tree nodes."""
    loc.snippet = _first_n_chars(loc.span_text or loc.raw_text, 200)

    # candidate label
    cand_label = ""
    if loc.candidate_texts:
        shown = ", ".join(loc.candidate_texts[:3])
        if len(loc.candidate_texts) > 3:
            shown += ", …"
        cand_label = f"({shown})"

    anchor_info = {
        ra.ctx: ra for ra in getattr(loc, "anchor_resolutions", [])
    }

    ctx_label = _ctx_label(loc.contexts, anchor_info)

    loc.summary = f"{loc.span_text} {cand_label} {ctx_label}".strip()


# ================================================================
# Dispatcher
# ================================================================

def summarize_node(node: ReviewNode) -> None:
    """Dispatch to correct summarizer."""
    if isinstance(node, PDPost):
        summarize_post(node)
    elif isinstance(node, PDSection):
        summarize_section(node)
    elif isinstance(node, PDEvent):
        summarize_event(node)
    elif isinstance(node, PDLocation):
        summarize_location(node)
    # Others are silently ignored (PDGroup? future)


# ================================================================
# Tree-wide summarization
# ================================================================

def summarize_tree(root: ReviewNode) -> None:
    """
    Recursively update summary + snippet across the tree.
    Only UI text fields are updated — no structural changes.
    """
    summarize_node(root)
    for child in root.children:
        summarize_tree(child)
