from __future__ import annotations

import sqlite3
from typing import Iterable, Callable

from sitrepc2.config.paths import records_path
from sitrepc2.lss.pipeline import run_lss_pipeline


def extract_posts_to_lss(
    ingest_post_ids: Iterable[int],
    *,
    progress_cb: Callable[[int, bool], None] | None = None,
    batch_size: int = 8,
) -> None:
    """
    Bridge between ingest and LSS.

    Executes LSS in batches to preserve spaCy efficiency.
    """

    ids = list(ingest_post_ids)
    if not ids:
        return

    with sqlite3.connect(records_path()) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            f"""
            SELECT id, text
            FROM ingest_posts
            WHERE id IN ({",".join("?" for _ in ids)})
            ORDER BY id
            """,
            ids,
        ).fetchall()

    posts = [
        {
            "id": row["id"],
            "text": row["text"],
        }
        for row in rows
    ]

    # ---- Run LSS in batches ----
    for i in range(0, len(posts), batch_size):
        batch = posts[i : i + batch_size]

        try:
            run_lss_pipeline(
                batch,
                batch_size=batch_size,
            )

            if progress_cb:
                for p in batch:
                    progress_cb(p["id"], True)

        except Exception:
            if progress_cb:
                for p in batch:
                    progress_cb(p["id"], False)
