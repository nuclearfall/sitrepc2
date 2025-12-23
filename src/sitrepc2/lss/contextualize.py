# src/sitrepc2/lss/contextualize.py

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List

from sitrepc2.lss.lss_scoping import LSSContextHint


def contextualize(
    *,
    context_hints: Iterable[LSSContextHint],
    section_ordinals: List[int],
    event_ordinals_by_section: dict[int, List[int]],
) -> List[LSSContextHint]:
    """
    Enforce mandatory context lattice.

    Rules:
      • Context must exist at POST, SECTION, EVENT levels
      • Child context overrides parent
      • Missing context is synthesized explicitly
      • No semantic resolution is performed
    """

    by_scope: dict[str, list[LSSContextHint]] = defaultdict(list)
    for hint in context_hints:
        by_scope[hint.scope].append(hint)

    out: list[LSSContextHint] = []

    # -------------------------------------------------
    # POST-level (always present if events exist)
    # -------------------------------------------------

    if not by_scope.get("POST"):
        out.append(
            LSSContextHint(
                ctx_kind="POST",
                text="",
                start_token=None,
                end_token=None,
                scope="POST",
                target_id=None,
                source="SYNTHETIC",
            )
        )
    else:
        out.extend(by_scope["POST"])

    # -------------------------------------------------
    # SECTION-level
    # -------------------------------------------------

    for sec in section_ordinals:
        if not any(
            h for h in by_scope.get("SECTION", [])
            if h.target_id == sec
        ):
            out.append(
                LSSContextHint(
                    ctx_kind="SECTION",
                    text="",
                    start_token=None,
                    end_token=None,
                    scope="SECTION",
                    target_id=sec,
                    source="SYNTHETIC",
                )
            )

    out.extend(by_scope.get("SECTION", []))

    # -------------------------------------------------
    # EVENT-level
    # -------------------------------------------------

    for sec, event_ordinals in event_ordinals_by_section.items():
        for ev in event_ordinals:
            if not any(
                h for h in by_scope.get("EVENT", [])
                if h.target_id == ev
            ):
                out.append(
                    LSSContextHint(
                        ctx_kind="EVENT",
                        text="",
                        start_token=None,
                        end_token=None,
                        scope="EVENT",
                        target_id=ev,
                        source="SYNTHETIC",
                    )
                )

    out.extend(by_scope.get("EVENT", []))

    # -------------------------------------------------
    # SERIES / LOCATION contexts already scoped
    # -------------------------------------------------

    out.extend(by_scope.get("SERIES", []))
    out.extend(by_scope.get("LOCATION", []))

    return out
