from __future__ import annotations

from pathlib import Path
import shutil

import typer

from sitrepc2.config.paths import (
    get_dotpath,
    db_path,
    seed_db_path,
    reference_root,
)

# NOTE: invoke_without_command=True lets `sitrepc2 init` run the callback
# directly instead of requiring a subcommand.
app = typer.Typer(
    help="Initialize a sitrepc2 workspace.",
    invoke_without_command=True,
)


@app.callback()
def init(
    ctx: typer.Context,
    path: Path = typer.Argument(
        Path("."),
        help="Project root to initialize (default: current directory).",
    ),
):
    """
    Initialize a sitrepc2 workspace at PATH.

    This will:
      • create a `.sitrepc2/` directory if it does not exist
      • copy the shipped seed database into `.sitrepc2/sitrepc2.db` if missing
      • optionally copy reference files (lexicon, tg channels) into `.sitrepc2/`
    """
    # When just showing help, don't actually do the work
    if ctx.invoked_subcommand is not None:
        # There *are* no subcommands right now, but this is the standard pattern
        return

    project_root = path.resolve()
    dot = get_dotpath(project_root)  # e.g. project_root / ".sitrepc2"
    dot.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Copy the seed database
    # ------------------------------------------------------------------
    dst_db = db_path(project_root)
    if dst_db.exists():
        typer.secho(f"Database already exists: {dst_db}", fg=typer.colors.YELLOW)
    else:
        src_db = seed_db_path()
        if not src_db.exists():
            raise RuntimeError(
                f"Seed database not found at {src_db}. "
                "Make sure sitrepc2_seed.db is packaged in sitrepc2/reference."
            )
        dst_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_db, dst_db)
        typer.secho(f"Copied seed DB: {src_db.name} → {dst_db}", fg=typer.colors.GREEN)

    # ------------------------------------------------------------------
    # 2. Optionally copy lexicon / tg channels
    # ------------------------------------------------------------------
    src_root = reference_root()
    for fname in ("war_lexicon.json", "tg_channels.jsonl"):
        src = src_root / fname
        if not src.exists():
            continue
        dst = dot / fname
        if dst.exists():
            continue
        shutil.copy2(src, dst)
        typer.secho(f"Copied reference file: {fname}", fg=typer.colors.GREEN)

    typer.secho("Workspace initialized.", fg=typer.colors.CYAN)
