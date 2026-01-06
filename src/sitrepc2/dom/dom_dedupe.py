from __future__ import annotations

import sqlite3
from collections import defaultdict
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
    dom_conn: sqlite3.Connection,
    context_hints: Iterable[LSSContextHint],
) -> Tuple[Tuple[str, int], ...]:
    """
    Context signature used ONLY for dedupe equivalence.

    Includes only:
      REGION / GROUP / DIRECTION
    Across the full dominance chain.
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
# Core dedupe engine
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
        SELECT dn.id, dp.text
        FROM dom_node dn
        LEFT JOIN dom_node_provenance dp ON dp.dom_node_id = dn.id
        JOIN dom_node_state st ON st.dom_node_id = dn.id
        WHERE dn.parent_id = ?
          AND dn.node_type = ?
          AND st.deduped = FALSE
        ORDER BY dn.sibling_order
        """,
        (parent_id, node_type),
    )

    seen: Dict[Tuple, int] = {}

    for node_id, text in cur.fetchall():
        key = key_fn(node_id, text)

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

    # ---------------------------------------------------------
    # SECTION
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT id
        FROM dom_node
        WHERE node_type = 'POST'
        """
    )

    for (post_id,) in cur.fetchall():
        _dedupe_children(
            dom_conn=dom_conn,
            parent_id=post_id,
            node_type="SECTION",
            key_fn=lambda nid, text: (
                _normalize(text or ""),
                _effective_context_signature(
                    dom_node_id=nid,
                    dom_conn=dom_conn,
                    context_hints=context_hints,
                ),
            ),
        )

    # ---------------------------------------------------------
    # EVENT
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT id
        FROM dom_node
        WHERE node_type IN ('POST', 'SECTION')
        """
    )

    for (parent_id,) in cur.fetchall():
        _dedupe_children(
            dom_conn=dom_conn,
            parent_id=parent_id,
            node_type="EVENT",
            key_fn=lambda nid, text: (
                _normalize(text or ""),
                _effective_context_signature(
                    dom_node_id=nid,
                    dom_conn=dom_conn,
                    context_hints=context_hints,
                ),
            ),
        )

    # ---------------------------------------------------------
    # LOCATION_SERIES
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT id
        FROM dom_node
        WHERE node_type = 'EVENT'
        """
    )

    for (event_id,) in cur.fetchall():
        def series_key(nid, _):
            c = dom_conn.cursor()
            c.execute(
                """
                SELECT dp.text
                FROM dom_node dn
                JOIN dom_node dpn ON dpn.parent_id = dn.id
                JOIN dom_node_provenance dp ON dp.dom_node_id = dpn.id
                WHERE dn.id = ?
                ORDER BY dpn.sibling_order
                """,
                (nid,),
            )
            items = [_normalize(r[0]) for r in c.fetchall()]
            return (
                tuple(items),
                _effective_context_signature(
                    dom_node_id=nid,
                    dom_conn=dom_conn,
                    context_hints=context_hints,
                ),
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
        """
        SELECT id
        FROM dom_node
        WHERE node_type = 'LOCATION_SERIES'
        """
    )

    for (series_id,) in cur.fetchall():
        _dedupe_children(
            dom_conn=dom_conn,
            parent_id=series_id,
            node_type="LOCATION",
            key_fn=lambda nid, text: (
                _normalize(text or ""),
                _effective_context_signature(
                    dom_node_id=nid,
                    dom_conn=dom_conn,
                    context_hints=context_hints,
                ),
            ),
        )

    dom_conn.commit()
