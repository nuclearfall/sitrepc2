# src/sitrepc2/cli/init_cmd.py
from __future__ import annotations

from pathlib import Path
import shutil
import typer

from sitrepc2.config.paths import (
    get_dotpath,
    seed_db_path,          # NEW: points to src/sitrepc2/reference/sitrepc2_seed.db
    db_path,               # destination path, i.e. .sitrepc2/sitrepc2.db
    reference_root,        # still useful for optional files like lexicon, tg channels
)

app = typer.Typer()


@app.command()
def init(path: Path = Path(".")):
    """
    Initialize a sitrepc2 workspace.

    Creates `.sitrepc2/` and copies the shipped seed database into place.
    Additional reference files (lexicon, tg channels) may also be copied
    if present in the package.
    """
    project_root = path.resolve()
    dot = get_dotpath(project_root)  # e.g. project_root / ".sitrepc2"
    dot.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------
    # 1. Copy the seed database
    # --------------------------------------------------------------
    dst_db = db_path(project_root)
    if dst_db.exists():
        typer.secho(f"Database already exists: {dst_db}", fg=typer.colors.YELLOW)
    else:
        src_db = seed_db_path()
        typer.secho(f"Copying seed DB: {src_db.name} → {dst_db}", fg=typer.colors.GREEN)
        shutil.copy2(src_db, dst_db)

    # --------------------------------------------------------------
    # 2. Optionally copy lexicon / tg channels (if needed)
    #    Files like: war_lexicon.json, tg_channels.jsonl
    # --------------------------------------------------------------
    src_root = reference_root()
    for fname in ("war_lexicon.json", "tg_channels.jsonl"):
        src = src_root / fname
        if src.exists():
            dst = dot / fname
            if not dst.exists():
                shutil.copy2(src, dst)
                typer.secho(f"Copied reference file: {fname}", fg=typer.colors.GREEN)

    typer.secho("Workspace initialized.", fg=typer.colors.CYAN)
