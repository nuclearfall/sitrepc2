from __future__ import annotations

from typing import Optional, List
from datetime import date

import typer
from rich import print

from sitrepc2.ingest.telegram import fetch_posts

app = typer.Typer(help="Fetch Telegram posts into the ingest database.")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _validate_iso_date(name: str, value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter(f"{name} must be YYYY-MM-DD, got {value!r}")
    return value


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

@app.callback()
def fetch_callback(
    *,
    start: str = typer.Option(
        ...,
        "--start",
        "-s",
        help="Start date (YYYY-MM-DD).",
        callback=lambda x: _validate_iso_date("start", x),
    ),
    end: Optional[str] = typer.Option(
        None,
        "--end",
        "-e",
        help="End date (YYYY-MM-DD). Defaults to start.",
        callback=lambda x: _validate_iso_date("end", x) if x else None,
    ),
    aliases: Optional[List[str]] = typer.Option(
        None,
        "--aliases",
        "-l",
        help="One or more source aliases (e.g. Russia, Ukraine, Rybar).",
    ),
    sources: Optional[List[str]] = typer.Option(
        None,
        "--sources",
        "-c",
        help="One or more source names (e.g. mod_russia_en, rybar_in_english).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-fetch posts even if they already exist in ingest_posts.",
    ),
):
    """
    Fetch Telegram posts.

    If neither --aliases nor --sources is provided, all active Telegram sources
    are fetched.
    """

    count = fetch_posts(
        start_date=start,
        end_date=end,
        aliases=aliases,
        source_name=sources,
        force=force,
    )

    print(f"[green]Inserted {count} Telegram posts into ingest DB[/green]")
