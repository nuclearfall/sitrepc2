from __future__ import annotations

import typer
from typing import Optional, List
from datetime import date

from rich import print
from sitrepc2.ingest.telegram import fetch_posts

app = typer.Typer(help="Fetch Telegram posts into the ingest database.")


def _validate_iso_date(name: str, value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError:
        raise typer.BadParameter(f"{name} must be YYYY-MM-DD, got {value!r}")
    return value


@app.callback()
def fetch_callback(
    source: str = typer.Argument(
        ...,
        help="'all' for all active sources or a single alias.",
    ),
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
):
    aliases: Optional[List[str]]
    if source.lower() == "all":
        aliases = None
    else:
        aliases = [source]

    count = fetch_posts(
        start_date=start,
        end_date=end,
        aliases=aliases,
    )

    print(f"[green]Inserted {count} Telegram posts into ingest DB[/green]")
