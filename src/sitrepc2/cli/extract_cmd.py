from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional, List

import typer
from rich import print

from sitrepc2.config.paths import records_path as records_db_path
from sitrepc2.lss.pipeline import run_lss_pipeline


def extract_callback(
    *,
    post_id: Optional[List[int]] = typer.Option(
        None,
        "--post-id",
        help="Process one or more ingest posts by ID. May be specified multiple times.",
    ),
    alias: Optional[str] = typer.Option(
        None, help="Filter by human-facing alias (e.g. Rybar)."
    ),
    publisher: Optional[str] = typer.Option(
        None, help="Filter by upstream publisher."
    ),
    pub_date: Optional[str] = typer.Option(
        None, help="Published date (UTC) in YYYY-MM-DD format."
    ),
    source: Optional[str] = typer.Option(
        None, help="Restrict to source (telegram, x, web, rss)."
    ),
    limit: Optional[int] = typer.Option(
        None, help="Maximum number of posts to process."
    ),
    reprocess: bool = typer.Option(
        False,
        "--reprocess",
        help="Force reprocessing even if LSS has already completed for a post.",
    ),
    keep_nonspatial: bool = typer.Option(
        False,
        "--keep-nonspatial",
        help="Retain non-spatial Holmes event matches for audit/debug (not persisted as LSS events).",
    ),
):
    """Select ingested posts and execute the LSS pipeline."""

    # -------------------------------------------------
    # Normalize inputs
    # -------------------------------------------------

    post_ids = post_id or []

    has_post_ids = len(post_ids) > 0
    has_other_filters = any([alias, publisher, pub_date, source])

    # -------------------------------------------------
    # Validate selector logic
    # -------------------------------------------------

    if has_post_ids and has_other_filters:
        raise typer.BadParameter(
            "--post-id cannot be combined with --alias, --publisher, --date, or --source."
        )

    if not has_post_ids and not has_other_filters:
        raise typer.BadParameter(
            "You must specify either one or more --post-id values, "
            "or at least one of --alias, --publisher, --date, or --source."
        )

    # -------------------------------------------------
    # DB helpers
    # -------------------------------------------------

    def _conn() -> sqlite3.Connection:
        con = sqlite3.connect(records_db_path())
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    def _parse_date_iso(value: str) -> tuple[str, str]:
        try:
            d = date.fromisoformat(value)
        except ValueError:
            raise typer.BadParameter("Date must be YYYY-MM-DD")

        start = f"{d.isoformat()}T00:00:00Z"
        end = f"{d.isoformat()}T23:59:59Z"
        return start, end

    # -------------------------------------------------
    # Build query
    # -------------------------------------------------

    clauses: List[str] = []
    params: List[object] = []

    if has_post_ids:
        placeholders = ",".join("?" for _ in post_ids)
        clauses.append(f"id IN ({placeholders})")
        params.extend(post_ids)

    if alias is not None:
        clauses.append("alias = ?")
        params.append(alias)

    if publisher is not None:
        clauses.append("publisher = ?")
        params.append(publisher)

    if source is not None:
        clauses.append("source = ?")
        params.append(source)

    if pub_date is not None:
        start, end = _parse_date_iso(pub_date)
        clauses.append("published_at BETWEEN ? AND ?")
        params.extend([start, end])

    where_sql = " AND ".join(clauses)

    sql = f"""
        SELECT id, text
        FROM ingest_posts
        WHERE {where_sql}
        ORDER BY published_at ASC
    """

    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    # -------------------------------------------------
    # Fetch posts
    # -------------------------------------------------

    with _conn() as con:
        rows = con.execute(sql, params).fetchall()

    if not rows:
        print("[yellow]No matching posts found.[/yellow]")
        raise typer.Exit()

    posts = [{"id": row["id"], "text": row["text"]} for row in rows]

    print(
        f"[green]Running LSS on {len(posts)} post(s)"
        + (" (reprocess enabled)" if reprocess else "")
        + "[/green]"
    )

    # -------------------------------------------------
    # Run LSS
    # -------------------------------------------------

    run_lss_pipeline(
        posts,
        reprocess=reprocess,
        keep_nonspatial=keep_nonspatial,
    )

    print("[bold green]LSS extraction complete.[/bold green]")
