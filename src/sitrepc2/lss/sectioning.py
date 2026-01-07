# src/sitrepc2/lss/sectioning.py

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


# ---------------------------------------------------------------------
# Data contract (pre-persistence)
# ---------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class LSSSection:
    """
    Pure structural section emitted by LSS sectioning.

    Identity is assigned only at persistence time.
    Token alignment is resolved downstream.
    """
    ordinal: int
    text: str
    start_char: int
    end_char: int


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
    Deterministically split a post into ordered structural sections.

    PURE structural logic:
      - no NLP
      - no semantics
      - no persistence
    """

    lines = post_text.splitlines(keepends=True)

    sections: list[tuple[int, int]] = []
    current_start: Optional[int] = None
    cursor = 0

    def flush(end: int):
        nonlocal current_start
        if current_start is not None and end > current_start:
            sections.append((current_start, end))
            current_start = None

    # -------------------------------------------------
    # Pass 1: heading-based splitting
    # -------------------------------------------------

    for line in lines:
        stripped = line.strip()

        if stripped and SECTION_HEADING_RE.match(stripped):
            flush(cursor)
            current_start = cursor
        elif current_start is None:
            current_start = cursor

        cursor += len(line)

    flush(cursor)

    # -------------------------------------------------
    # Pass 2: paragraph-based splitting (double newline)
    # -------------------------------------------------

    final_spans: list[tuple[int, int]] = []

    for start, end in sections:
        block_text = post_text[start:end]

        if "\n\n" in block_text:
            rel_cursor = 0
            for para in block_text.split("\n\n"):
                para = para.strip()
                if not para:
                    continue

                para_start = block_text.find(para, rel_cursor)
                if para_start == -1:
                    continue

                abs_start = start + para_start
                abs_end = abs_start + len(para)

                final_spans.append((abs_start, abs_end))
                rel_cursor = para_start + len(para)
        else:
            final_spans.append((start, end))


    # -------------------------------------------------
    # Emit ordered sections
    # -------------------------------------------------

    out: list[LSSSection] = []

    for idx, (start, end) in enumerate(final_spans):
        out.append(
            LSSSection(
                ordinal=idx,
                text=post_text[start:end].strip(),
                start_char=start,
                end_char=end,
            )
        )

    return out
