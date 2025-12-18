# src/sitrepc2/cli/source_cmd.py
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import typer
from rich import print
from rich.table import Table

from sitrepc2.config.paths import current_root, sources_path

app = typer.Typer(help="Manage social media source channels (sources.jsonl).")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _channel_file() -> Path:
    """Return the workspace sources.jsonl path (under .sitrepc2/)."""
    root = current_root()
    return sources_path(root)


def _normalize_name(name: str) -> str:
    """Strip leading '@' and whitespace from channel name."""
    return name.lstrip("@").strip()


def _load_channels() -> List[Dict[str, Any]]:
    path = _channel_file()
    if not path.exists():
        # No file yet → treat as empty list
        return []
    channels: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            channels.append(json.loads(line))
    return channels


def _save_channels(channels: List[Dict[str, Any]]) -> None:
    path = _channel_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ch in channels:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")


def _find_indices(
    channels: List[Dict[str, Any]],
    key: str,
) -> List[int]:
    """
    Find indices where alias or channel_name matches the key
    (case-sensitive for now, but normalize '@' on channel_name).
    """
    key = key.strip()
    norm_key = _normalize_name(key)
    idxs: List[int] = []
    for i, ch in enumerate(channels):
        if ch.get("alias") == key:
            idxs.append(i)
        elif _normalize_name(str(ch.get("channel_name", ""))) == norm_key:
            idxs.append(i)
    return idxs


def _print_channels(channels: List[Dict[str, Any]]) -> None:
    if not channels:
        print("[yellow]No sources configured.[/yellow]")
        return

    table = Table(title="Sources (sources.jsonl)")
    table.add_column("channel_name")
    table.add_column("alias")
    table.add_column("lang")
    table.add_column("active", justify="center")

    for ch in channels:
        table.add_row(
            str(ch.get("channel_name", "")),
            str(ch.get("alias", "")),
            str(ch.get("channel_lang", "")),
            "✅" if ch.get("active") else "❌",
        )

    print(table)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command("list")
def list_sources(
    active_only: bool = typer.Option(
        False,
        "--active-only",
        help="Show only active sources.",
    )
):
    """
    List all configured social-media sources from sources.jsonl.
    """
    channels = _load_channels()
    if active_only:
        channels = [ch for ch in channels if ch.get("active")]
    _print_channels(channels)


@app.command("add")
def add_source(
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Channel name or handle (e.g. @rybar_en or rybar_en).",
    ),
    alias: Optional[str] = typer.Option(
        None,
        "--alias",
        "-a",
        help="Short alias (e.g. rybar).",
    ),
    lang: Optional[str] = typer.Option(
        None,
        "--lang",
        "-l",
        help="Language code (e.g. en, uk, ru).",
    ),
    active: bool = typer.Option(
        True,
        "--active",
        help="Whether this source should be active (default: true).",
    ),
    entry: Optional[str] = typer.Option(
        None,
        "--entry",
        help=(
            "Optional compact form: "
            "'\"@name alias lang active\"'. "
            "Example: --entry \"@rybar_en rybar en true\""
        ),
    ),
):
    """
    Add a new source.

    You can either specify fields individually:

        sitrepc2 source add --name @rybar_en --alias rybar --lang en --active true

    or use the compact entry form:

        sitrepc2 source add --entry "@rybar_en rybar en true"
    """

    # Parse compact entry form if provided
    if entry:
        parts = entry.split()
        if len(parts) != 4:
            raise typer.BadParameter(
                "Entry must have exactly 4 fields: <name> <alias> <lang> <active>"
            )
        name, alias, lang, active_str = parts
        active = active_str.lower() in ("1", "true", "yes", "y")

    # Validate explicit fields
    if not name:
        raise typer.BadParameter("Missing --name (or use --entry).")
    if not alias:
        raise typer.BadParameter("Missing --alias (or use --entry).")
    if not lang:
        raise typer.BadParameter("Missing --lang (or use --entry).")

    channel_name = _normalize_name(name)
    alias = alias.strip()
    lang = lang.strip()

    channels = _load_channels()

    # Prevent duplicates by alias or channel_name
    for ch in channels:
        if _normalize_name(str(ch.get("channel_name", ""))) == channel_name:
            raise typer.BadParameter(
                f"Channel name '{channel_name}' already exists (alias={ch.get('alias')})."
            )
        if ch.get("alias") == alias:
            raise typer.BadParameter(
                f"Alias '{alias}' already exists (channel={ch.get('channel_name')})."
            )

    new_entry = {
        "channel_name": channel_name,
        "alias": alias,
        "channel_lang": lang,
        "active": bool(active),
    }
    channels.append(new_entry)
    _save_channels(channels)

    print(f"[green]Added source:[/green] {new_entry}")


@app.command("remove")
def remove_source(
    key: str = typer.Argument(
        ...,
        help="Alias or channel_name of the source to remove.",
    )
):
    """
    Remove a source by alias or channel_name.
    """
    channels = _load_channels()
    idxs = _find_indices(channels, key)
    if not idxs:
        print(f"[red]No source found for key '{key}'.[/red]")
        raise typer.Exit(code=1)

    remaining: List[Dict[str, Any]] = [
        ch for i, ch in enumerate(channels) if i not in idxs
    ]
    _save_channels(remaining)

    print(
        f"[green]Removed {len(idxs)} source(s) matching '{key}'.[/green]"
    )


@app.command("activate")
def activate_source(
    key: str = typer.Argument(
        ...,
        help="Alias or channel_name of the source to activate.",
    )
):
    """
    Mark one or more sources as active.
    """
    channels = _load_channels()
    idxs = _find_indices(channels, key)
    if not idxs:
        print(f"[red]No source found for key '{key}'.[/red]")
        raise typer.Exit(code=1)

    for i in idxs:
        channels[i]["active"] = True

    _save_channels(channels)
    print(f"[green]Activated {len(idxs)} source(s) matching '{key}'.[/green]")


@app.command("deactivate")
def deactivate_source(
    key: str = typer.Argument(
        ...,
        help="Alias or channel_name of the source to deactivate.",
    )
):
    """
    Mark one or more sources as inactive.
    """
    channels = _load_channels()
    idxs = _find_indices(channels, key)
    if not idxs:
        print(f"[red]No source found for key '{key}'.[/red]")
        raise typer.Exit(code=1)

    for i in idxs:
        channels[i]["active"] = False

    _save_channels(channels)
    print(f"[green]Deactivated {len(idxs)} source(s) matching '{key}'.[/green]")
