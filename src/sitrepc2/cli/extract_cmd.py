# src/sitrepc2/cli/extract_cmd.py
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional, List

import typer
from rich import print

from sitrepc2.config.paths import get_records_db_path
from sitrepc2.lss.pipeline import run_lss_pipeline


def extract_callback(
    *,
    post_id: Optional[int] = typer.Option(
        None, help="Process a single ingest post by ID."
    ),
    alias: Optional[str] = typer.Option(
        None, help="Filter by human-facing alias (e.g. Rybar)."
    ),
    publisher: Optional[str] = typer.Option(
        None, help="Filter by upstream publisher."
    ),
    date: Optional[str] = typer.Option(
        None, help="Published date (UTC) in YYYYMMDD format."
    ),
    source: Optional[str] = typer.Option(
        None, help="Restrict to source (telegram, x, web, rss)."
    ),
    limit: Optional[int] = typer.Option(
        None, help="Maximum number of posts to process."
    ),
):
    """Select ingested posts and execute the LSS pipeline."""

    # -------------------------------------------------
    # Validate selector logic
    # -------------------------------------------------

    selectors = [post_id is not None, alias is not None, publisher is not None]
    if sum(selectors) != 1:
        raise typer.BadParameter(
            "Exactly one of --post-id, --alias, or --publisher must be provided."
        )

    # -------------------------------------------------
    # DB helpers
    # -------------------------------------------------

    def _conn() -> sqlite3.Connection:
        con = sqlite3.connect(get_records_db_path())
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    def _parse_date_yyyymmdd(value: str) -> tuple[str, str]:
        try:
            dt = datetime.strptime(value, "%Y%m%d")
        except ValueError:
            raise typer.BadParameter("Date must be YYYYMMDD")

        start = dt.strftime("%Y-%m-%dT00:00:00Z")
        end = dt.strftime("%Y-%m-%dT23:59:59Z")
        return start, end

    # -------------------------------------------------
    # Build query
    # -------------------------------------------------

    clauses: List[str] = []
    params: List[object] = []

    if post_id is not None:
        clauses.append("id = ?")
        params.append(post_id)

    if alias is not None:
        clauses.append("alias = ?")
        params.append(alias)

    if publisher is not None:
        clauses.append("publisher = ?")
        params.append(publisher)

    if source is not None:
        clauses.append("source = ?")
        params.append(source)

    if date is not None:
        start, end = _parse_date_yyyymmdd(date)
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

    print(f"[green]Running LSS on {len(posts)} post(s)[/green]")

    # -------------------------------------------------
    # Run LSS
    # -------------------------------------------------

    run_lss_pipeline(posts)

    print("[bold green]LSS extraction complete.[/bold green]")
