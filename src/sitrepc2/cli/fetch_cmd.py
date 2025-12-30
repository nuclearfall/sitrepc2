from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, List
from datetime import date

import typer
from rich import print

from sitrepc2.ingest.telegram import fetch_posts
from sitrepc2.config.paths import sources_path

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


def _load_sources() -> List[dict]:
    path = Path(sources_path())
    sources = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sources.append(json.loads(line))
    return sources


def _resolve_source_selector(source: str) -> Optional[List[str]]:
    """
    Resolve user input into a list of canonical aliases.

    Accepts:
      - 'all'
      - alias (e.g. 'Russia')
      - source_name (e.g. 'mod_russia_en')
    """

    if source.lower() == "all":
        return None

    sources = _load_sources()

    matches = [
        s for s in sources
        if s.get("active")
        and s.get("source_kind") == "TELEGRAM"
        and (
            s.get("alias") == source
            or s.get("source_name") == source
        )
    ]

    if not matches:
        known = sorted(
            {s["alias"] for s in sources if s.get("active")}
            | {s["source_name"] for s in sources if s.get("active")}
        )
        raise typer.BadParameter(
            f"No active Telegram source matches {source!r}.\n"
            f"Known sources: {', '.join(known)}"
        )

    # fetch_posts() expects aliases
    return [s["alias"] for s in matches]


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

@app.callback()
def fetch_callback(
    source: str = typer.Argument(
        ...,
        help="'all' for all active sources, or a single alias or source name.",
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
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-fetch posts even if they already exist in ingest_posts.",
    ),
):
    aliases = _resolve_source_selector(source)

    count = fetch_posts(
        start_date=start,
        end_date=end,
        aliases=aliases,
        force=force,
    )

    print(f"[green]Inserted {count} Telegram posts into ingest DB[/green]")
