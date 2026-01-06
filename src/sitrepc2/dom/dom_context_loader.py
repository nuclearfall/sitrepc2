from __future__ import annotations

import sqlite3
from typing import List

from sitrepc2.lss.lss_scoping import LSSContextHint


def load_lss_context_hints(
    *,
    conn: sqlite3.Connection,
    lss_run_id: int,
) -> List[LSSContextHint]:
    """
    Load persisted LSS context hints for a run.

    Contract:
      • Lossless rehydration
      • No synthesis
      • No inference
      • No filtering
    """

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            ctx_kind,
            text,
            start_token,
            end_token,
            scope,
            target_id,
            source
        FROM lss_context_hints
        WHERE lss_run_id = ?
        ORDER BY id
        """,
        (lss_run_id,),
    )

    rows = cur.fetchall()

    return [
        LSSContextHint(
            ctx_kind=ctx_kind,
            text=text,
            start_token=start_token,
            end_token=end_token,
            scope=scope,
            target_id=target_id,
            source=source,
        )
        for (
            ctx_kind,
            text,
            start_token,
            end_token,
            scope,
            target_id,
            source,
        ) in rows
    ]
