from __future__ import annotations

import sqlite3


def recompute_commit_eligibility(
    *,
    conn: sqlite3.Connection,
    dom_snapshot_id: int,
) -> None:
    """
    Derive commit eligibility per DOM node.

    Rules:
      • LOCATION nodes must be resolved
      • Deselected nodes are ineligible
    """

    cur = conn.cursor()

    # Clear previous eligibility
    cur.execute(
        """
        DELETE FROM dom_commit_eligibility
        WHERE dom_snapshot_id = ?
        """,
        (dom_snapshot_id,),
    )

    # Evaluate eligibility
    cur.execute(
        """
        SELECT
            dn.id,
            st.selected,
            st.resolved
        FROM dom_node dn
        JOIN dom_node_state st
          ON st.dom_node_id = dn.id
         AND st.dom_snapshot_id = ?
        """,
        (dom_snapshot_id,),
    )

    for node_id, selected, resolved in cur.fetchall():
        if not selected:
            eligible = False
            reason = "DESELECTED"
        elif resolved is False:
            eligible = False
            reason = "UNRESOLVED"
        else:
            eligible = True
            reason = None

        cur.execute(
            """
            INSERT INTO dom_commit_eligibility (
                dom_snapshot_id,
                dom_node_id,
                eligible,
                reason
            )
            VALUES (?, ?, ?, ?)
            """,
            (dom_snapshot_id, node_id, eligible, reason),
        )

    conn.commit()
