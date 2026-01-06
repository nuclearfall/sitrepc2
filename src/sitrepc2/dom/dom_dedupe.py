from __future__ import annotations

import sqlite3
from typing import Dict, Iterable, List, Tuple

from sitrepc2.lss.lss_scoping import LSSContextHint


# ============================================================
# Utilities
# ============================================================

def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _effective_context_signature(
    *,
    dom_node_id: int,
    context_hints: Iterable[LSSContextHint],
) -> Tuple[Tuple[str, int], ...]:
    """
    Context signature used ONLY for dedupe equivalence.
    Snapshot scoping is enforced by caller.
    """
    sig = []
    for h in context_hints:
        if h.ctx_kind in {"REGION", "GROUP", "DIRECTION"}:
            sig.append((h.ctx_kind, h.target_id or -1))
    return tuple(sorted(sig))


def _mark_deduped(
    *,
    conn: sqlite3.Connection,
    dom_snapshot_id: int,
    dup_id: int,
    canonical_id: int,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE dom_node_state
        SET deduped = TRUE,
            dedupe_target_id = ?
        WHERE dom_snapshot_id = ?
          AND dom_node_id = ?
        """,
        (canonical_id, dom_snapshot_id, dup_id),
    )


# ============================================================
# Core dedupe engine
# ============================================================

def _dedupe_children(
    *,
    conn: sqlite3.Connection,
    dom_snapshot_id: int,
    parent_id: int,
    node_type: str,
    key_fn,
) -> None:
    """
    Generic sibling dedupe under a single parent, snapshot-local.
    """
    cur = conn.cursor()

    cur.execute(
        """
        SELECT dn.id, dp.text
        FROM dom_node dn
        LEFT JOIN dom_node_provenance dp ON dp.dom_node_id = dn.id
        JOIN dom_node_state st
          ON st.dom_node_id = dn.id
         AND st.dom_snapshot_id = ?
        WHERE dn.parent_id = ?
          AND dn.node_type = ?
          AND st.deduped = FALSE
        ORDER BY dn.sibling_order
        """,
        (dom_snapshot_id, parent_id, node_type),
    )

    seen: Dict[Tuple, int] = {}

    for node_id, text in cur.fetchall():
        key = key_fn(node_id, text)

        if key in seen:
            _mark_deduped(
                conn=conn,
                dom_snapshot_id=dom_snapshot_id,
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
    dom_snapshot_id: int,
    context_hints: List[LSSContextHint],
) -> None:
    """
    Snapshot-local DOM deduplication.

    Must be run AFTER dom_ingest
    Must be run BEFORE dom_scoping
    """

    cur = conn.cursor()

    # ---------------------------------------------------------
    # POST → SECTION
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT dn.id
        FROM dom_node dn
        JOIN dom_snapshot ds ON ds.dom_post_id = dn.dom_post_id
        WHERE dn.node_type = 'POST'
          AND ds.id = ?
        """,
        (dom_snapshot_id,),
    )

    for (post_id,) in cur.fetchall():
        _dedupe_children(
            conn=conn,
            dom_snapshot_id=dom_snapshot_id,
            parent_id=post_id,
            node_type="SECTION",
            key_fn=lambda nid, text: (
                _normalize(text or ""),
                _effective_context_signature(
                    dom_node_id=nid,
                    context_hints=context_hints,
                ),
            ),
        )

    # ---------------------------------------------------------
    # SECTION / POST → EVENT
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT dn.id
        FROM dom_node dn
        JOIN dom_snapshot ds ON ds.dom_post_id = dn.dom_post_id
        WHERE dn.node_type IN ('POST', 'SECTION')
          AND ds.id = ?
        """,
        (dom_snapshot_id,),
    )

    for (parent_id,) in cur.fetchall():
        _dedupe_children(
            conn=conn,
            dom_snapshot_id=dom_snapshot_id,
            parent_id=parent_id,
            node_type="EVENT",
            key_fn=lambda nid, text: (
                _normalize(text or ""),
                _effective_context_signature(
                    dom_node_id=nid,
                    context_hints=context_hints,
                ),
            ),
        )

    # ---------------------------------------------------------
    # EVENT → LOCATION_SERIES
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT dn.id
        FROM dom_node dn
        JOIN dom_snapshot ds ON ds.dom_post_id = dn.dom_post_id
        WHERE dn.node_type = 'EVENT'
          AND ds.id = ?
        """,
        (dom_snapshot_id,),
    )

    for (event_id,) in cur.fetchall():

        def series_key(nid, _):
            c = conn.cursor()
            c.execute(
                """
                SELECT dp.text
                FROM dom_node child
                JOIN dom_node_provenance dp ON dp.dom_node_id = child.id
                WHERE child.parent_id = ?
                ORDER BY child.sibling_order
                """,
                (nid,),
            )
            items = [_normalize(r[0]) for r in c.fetchall()]
            return (
                tuple(items),
                _effective_context_signature(
                    dom_node_id=nid,
                    context_hints=context_hints,
                ),
            )

        _dedupe_children(
            conn=conn,
            dom_snapshot_id=dom_snapshot_id,
            parent_id=event_id,
            node_type="LOCATION_SERIES",
            key_fn=series_key,
        )

    # ---------------------------------------------------------
    # LOCATION_SERIES → LOCATION
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT dn.id
        FROM dom_node dn
        JOIN dom_snapshot ds ON ds.dom_post_id = dn.dom_post_id
        WHERE dn.node_type = 'LOCATION_SERIES'
          AND ds.id = ?
        """,
        (dom_snapshot_id,),
    )

    for (series_id,) in cur.fetchall():
        _dedupe_children(
            conn=conn,
            dom_snapshot_id=dom_snapshot_id,
            parent_id=series_id,
            node_type="LOCATION",
            key_fn=lambda nid, text: (
                _normalize(text or ""),
                _effective_context_signature(
                    dom_node_id=nid,
                    context_hints=context_hints,
                ),
            ),
        )

    conn.commit()
