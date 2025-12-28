from __future__ import annotations

import sqlite3
from datetime import datetime, date, timezone
from typing import Optional, List

import typer
from rich import print

from sitrepc2.config.paths import records_path as records_db_path
from sitrepc2.dom.dom_ingest import dom_ingest

app = typer.Typer(help="DOM ingestion and lifecycle commands")


# ---------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# dom ingest command
# ---------------------------------------------------------------------

@app.command("ingest")
def dom_ingest_cmd(
    *,
    post_id: Optional[int] = typer.Option(
        None, help="Ingest a single post by ID."
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
    reingest: bool = typer.Option(
        False,
        "--reingest",
        help="Recreate DOM even if it already exists (ERROR if schema forbids).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be ingested without writing DOM records.",
    ),
):
    """
    Materialize DOM structure from completed LSS runs.

    Operates on *sets of posts* using the same selector semantics
    as `sitrepc2 extract`.
    """

    # -------------------------------------------------
    # Validate selector logic (same as extract)
    # -------------------------------------------------

    if post_id is not None:
        if any([alias, publisher, pub_date, source]):
            raise typer.BadParameter(
                "--post-id cannot be combined with other filters."
            )
    else:
        if not any([alias, publisher, pub_date, source]):
            raise typer.BadParameter(
                "At least one of --date, --alias, --publisher, or --source must be provided."
            )

    # -------------------------------------------------
    # Build ingest_posts query
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

    if pub_date is not None:
        start, end = _parse_date_iso(pub_date)
        clauses.append("published_at BETWEEN ? AND ?")
        params.extend([start, end])

    where_sql = " AND ".join(clauses)

    sql = f"""
        SELECT id
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
        post_rows = con.execute(sql, params).fetchall()

    if not post_rows:
        print("[yellow]No matching posts found.[/yellow]")
        raise typer.Exit()

    post_ids = [row["id"] for row in post_rows]

    print(f"[green]Evaluating {len(post_ids)} post(s) for DOM ingest[/green]")

    # -------------------------------------------------
    # Process each post
    # -------------------------------------------------

    created_at = datetime.now(timezone.utc)

    stats = {
        "ingested": 0,
        "skipped_no_lss": 0,
        "skipped_existing": 0,
        "failed": 0,
    }

    for pid in post_ids:
        with _conn() as con:
            cur = con.cursor()

            # Latest completed LSS run
            cur.execute(
                """
                SELECT id
                FROM lss_runs
                WHERE ingest_post_id = ?
                  AND completed_at IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT 1
                """,
                (pid,),
            )
            row = cur.fetchone()

            if row is None:
                print(f"[yellow]Post {pid}: no completed LSS run[/yellow]")
                stats["skipped_no_lss"] += 1
                continue

            lss_run_id = row["id"]

            # Existing DOM?
            cur.execute(
                """
                SELECT id
                FROM dom_post
                WHERE ingest_post_id = ?
                  AND lss_run_id = ?
                """,
                (pid, lss_run_id),
            )

            if cur.fetchone() is not None and not reingest:
                print(f"[cyan]Post {pid}: DOM already exists[/cyan]")
                stats["skipped_existing"] += 1
                continue

            if dry_run:
                print(
                    f"[blue]Post {pid}: would ingest DOM from LSS run {lss_run_id}[/blue]"
                )
                continue

            try:
                dom_ingest(
                    conn=con,
                    ingest_post_id=pid,
                    lss_run_id=lss_run_id,
                    created_at=created_at,
                )
                con.commit()
                print(
                    f"[green]Post {pid}: DOM ingested (LSS run {lss_run_id})[/green]"
                )
                stats["ingested"] += 1

            except Exception as e:
                con.rollback()
                print(
                    f"[red]Post {pid}: DOM ingest failed: {e}[/red]"
                )
                stats["failed"] += 1

    # -------------------------------------------------
    # Summary
    # -------------------------------------------------

    print("\n[bold]DOM ingest summary[/bold]")
    for k, v in stats.items():
        print(f"  {k}: {v}")
