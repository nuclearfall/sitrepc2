# src/sitrepc2/cli/fetch_cmd.py
# src/sitrepc2/cli/fetch_cmd.py
from __future__ import annotations

import typer
from pathlib import Path
from typing import List, Optional
from datetime import date

from rich import print
from sitrepc2.config.paths import current_root, tg_channels_path
from sitrepc2.ingest.telegram import fetch_posts

app = typer.Typer(help="Fetch Telegram posts into interim storage.")

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
        help="'all' for all active channels, or a single alias/channel (e.g. rybar).",
    ),
    start: str = typer.Option(
        ...,
        "--start",
        "-s",
        help="Start date (YYYY-MM-DD, inclusive).",
        callback=lambda x: _validate_iso_date("start", x),
    ),
    end: Optional[str] = typer.Option(
        None,
        "--end",
        "-e",
        help="End date (YYYY-MM-DD, inclusive). Defaults to start.",
        callback=lambda x: _validate_iso_date("end", x) if x else None,
    ),
    blacklist: List[str] = typer.Option(
        [],
        "--blacklist",
        help="Words to *exclude* (case-insensitive).",
    ),
    whitelist: List[str] = typer.Option(
        [],
        "--whitelist",
        help="Words to *require* (case-insensitive).",
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Optional output path for posts.jsonl.",
    ),
):
    """
    Fetch Telegram posts into data/interim.

    Examples:

        sitrepc2 fetch rybar --start 2025-12-01
        sitrepc2 fetch all --start 2025-12-01
        sitrepc2 fetch all --start 2025-12-01 --blacklist word1 word2
    """
    root = current_root()
    channels_path = tg_channels_path(root)

    if not channels_path.exists():
        raise typer.BadParameter(
            f"Channels file not found: {channels_path}. "
            "Run 'sitrepc2 init' and 'sitrepc2 source add' first."
        )

    if source.lower() == "all":
        aliases = None
    else:
        aliases = [source]

    output_path, records = fetch_posts(
        start_date=start,
        end_date=end,
        aliases=aliases,
        blacklist=blacklist or None,
        whitelist=whitelist or None,
        channels_path=channels_path,
        out_path=out,
    )

    print(
        f"[green]Fetched {len(records)} posts[/green] from "
        f"[cyan]{source}[/cyan] → [magenta]{output_path}[/magenta]"
    )
