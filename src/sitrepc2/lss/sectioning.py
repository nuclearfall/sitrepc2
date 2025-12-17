# src/sitrepc2/lss/sectioning.py

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


# ---------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class LSSSection:
    section_id: str
    position: int
    text: str


# ---------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------

SECTION_HEADING_RE = re.compile(
    r"""
    ^\s*
    (?:[-•*]+|\#{1,6})?\s*
    [A-ZА-ЯЁІЇЄҐ][^:\n]{2,}
    :?\s*$
    """,
    re.VERBOSE,
)


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def split_into_sections(post_text: str) -> List[LSSSection]:
    """
    Deterministically split a post into ordered sections.

    Rules (in order):
      1. Heading-like lines start new sections
      2. Blank-line separation is preserved
      3. Long sections may be split by paragraph blocks

    This function is PURE:
      - no NLP
      - no semantics
      - no context inference
    """

    lines = post_text.splitlines()
    sections: list[list[str]] = []
    current: list[str] = []

    def flush():
        nonlocal current
        if current:
            sections.append(current)
            current = []

    # -------------------------------------------------
    # Pass 1: heading-based splitting
    # -------------------------------------------------

    for line in lines:
        stripped = line.strip()

        if stripped and SECTION_HEADING_RE.match(stripped):
            flush()
            current.append(line)
        else:
            current.append(line)

    flush()

    # -------------------------------------------------
    # Pass 2: paragraph fallback for very long sections
    # -------------------------------------------------

    final_sections: list[str] = []

    for block in sections:
        text = "\n".join(block).strip()

        if len(text) > 800 and "\n\n" in text:
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            final_sections.extend(paragraphs)
        else:
            final_sections.append(text)

    # -------------------------------------------------
    # Emit structured sections
    # -------------------------------------------------

    out: list[LSSSection] = []
    for idx, text in enumerate(final_sections):
        out.append(
            LSSSection(
                section_id=f"S{idx}",
                position=idx,
                text=text,
            )
        )

    return out
