from __future__ import annotations

import sqlite3
from typing import Iterable, Dict, Set

from sitrepc2.lss.lss_scoping import LSSContextHint
from sitrepc2.dom.dom_scoping import collect_context_chain


def materialize_dom_context(
    *,
    dom_conn: sqlite3.Connection,
    dom_snapshot_id: int,
    context_hints: Iterable[LSSContextHint],
) -> None:
    """
    Materialize effective context per DOM node into dom_context.

    Rules:
      • Snapshot-scoped
      • Dominance-resolved (LOCATION → SERIES → EVENT → SECTION → POST)
      • No inference
      • No synthesis
      • Idempotent per snapshot
    """

    cur = dom_conn.cursor()

    # ---------------------------------------------------------
    # Guard: do not double-materialize
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT 1
        FROM dom_context
        WHERE dom_snapshot_id = ?
        LIMIT 1
        """,
        (dom_snapshot_id,),
    )

    if cur.fetchone() is not None:
        return

    # ---------------------------------------------------------
    # Iterate all DOM nodes in snapshot
    # ---------------------------------------------------------

    cur.execute(
        """
        SELECT dn.id
        FROM dom_node dn
        JOIN dom_node_state st
          ON st.dom_node_id = dn.id
         AND st.dom_snapshot_id = ?
        """,
        (dom_snapshot_id,),
    )

    node_ids = [row[0] for row in cur.fetchall()]

    for node_id in node_ids:
        ctx_map: Dict[str, Set[int]] = collect_context_chain(
            dom_snapshot_id=dom_snapshot_id,
            node_id=node_id,
            dom_conn=dom_conn,
            context_hints=context_hints,
        )

        for ctx_kind, values in ctx_map.items():
            for value in values:
                cur.execute(
                    """
                    INSERT INTO dom_context (
                        dom_snapshot_id,
                        dom_node_id,
                        ctx_kind,
                        ctx_value,
                        overridden
                    )
                    VALUES (?, ?, ?, ?, FALSE)
                    """,
                    (
                        dom_snapshot_id,
                        node_id,
                        ctx_kind,
                        str(value),
                    ),
                )

    dom_conn.commit()
