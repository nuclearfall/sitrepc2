from __future__ import annotations

import sqlite3
from typing import Dict, Iterable, List, Tuple

from sitrepc2.lss.lss_scoping import LSSContextHint


# ============================================================
# Context signature (unchanged)
# ============================================================

def _effective_context_signature(
    *,
    context_hints: Iterable[LSSContextHint],
) -> Tuple[Tuple[str, int], ...]:
    """
    Context signature used ONLY for dedupe equivalence.

    Includes only:
      REGION / GROUP / DIRECTION
    """

    sig = []

    for h in context_hints:
        if h.ctx_kind not in {"REGION", "GROUP", "DIRECTION"}:
            continue
        sig.append((h.ctx_kind, h.target_id or -1))

    return tuple(sorted(sig))


def _mark_deduped(
    *,
    dom_conn: sqlite3.Connection,
    dup_id: int,
    canonical_id: int,
) -> None:
    cur = dom_conn.cursor()
    cur.execute(
        """
        UPDATE dom_node_state
        SET deduped = TRUE,
            dedupe_target_id = ?
        WHERE dom_node_id = ?
        """,
        (canonical_id, dup_id),
    )


# ============================================================
# Core dedupe helper
# ============================================================

def _dedupe_children(
    *,
    dom_conn: sqlite3.Connection,
    parent_id: int,
    node_type: str,
    key_fn,
) -> None:
    """
    Generic sibling dedupe under a single parent.
    """

    cur = dom_conn.cursor()

    cur.execute(
        """
        SELECT dn.id
        FROM dom_node dn
        JOIN dom_node_state st
          ON st.dom_node_id = dn.id
        WHERE dn.parent_id = ?
          AND dn.node_type = ?
          AND st.deduped = FALSE
        ORDER BY dn.sibling_order
        """,
        (parent_id, node_type),
    )

    seen: Dict[Tuple, int] = {}

    for (node_id,) in cur.fetchall():
        key = key_fn(node_id)

        if key in seen:
            _mark_deduped(
                dom_conn=dom_conn,
                dup_id=node_id,
                canonical_id=seen[key],
            )
        else:
            seen[key] = node_id


# ============================================================
# Public API
# ============================================================

def dom_dedupe(
    *,
    dom_conn: sqlite3.Connection,
    context_hints: List[LSSContextHint],
) -> None:
    """
    Hierarchy-wide DOM deduplication.

    Must be run AFTER dom_ingest
    Must be run BEFORE dom_scoping
    """

    cur = dom_conn.cursor()
    ctx_sig = _effective_context_signature(context_hints=context_hints)

    # ---------------------------------------------------------
    # SECTION
    # ---------------------------------------------------------

    cur.execute(
        "SELECT id FROM dom_node WHERE node_type = 'POST'"
    )

    for (post_id,) in cur.fetchall():
        _dedupe_children(
            dom_conn=dom_conn,
            parent_id=post_id,
            node_type="SECTION",
            key_fn=lambda nid: (nid, ctx_sig),
        )

    # ---------------------------------------------------------
    # EVENT
    # ---------------------------------------------------------

    cur.execute(
        "SELECT id FROM dom_node WHERE node_type IN ('POST', 'SECTION')"
    )

    for (parent_id,) in cur.fetchall():
        _dedupe_children(
            dom_conn=dom_conn,
            parent_id=parent_id,
            node_type="EVENT",
            key_fn=lambda nid: (nid, ctx_sig),
        )

    # ---------------------------------------------------------
    # LOCATION_SERIES
    # ---------------------------------------------------------

    cur.execute(
        "SELECT id FROM dom_node WHERE node_type = 'EVENT'"
    )

    for (event_id,) in cur.fetchall():
        def series_key(series_node_id: int):
            c = dom_conn.cursor()
            c.execute(
                """
                SELECT child.id
                FROM dom_node child
                WHERE child.parent_id = ?
                ORDER BY child.sibling_order
                """,
                (series_node_id,),
            )
            return (
                tuple(r[0] for r in c.fetchall()),
                ctx_sig,
            )

        _dedupe_children(
            dom_conn=dom_conn,
            parent_id=event_id,
            node_type="LOCATION_SERIES",
            key_fn=series_key,
        )

    # ---------------------------------------------------------
    # LOCATION
    # ---------------------------------------------------------

    cur.execute(
        "SELECT id FROM dom_node WHERE node_type = 'LOCATION_SERIES'"
    )

    for (series_id,) in cur.fetchall():
        _dedupe_children(
            dom_conn=dom_conn,
            parent_id=series_id,
            node_type="LOCATION",
            key_fn=lambda nid: (nid, ctx_sig),
        )

    dom_conn.commit()
