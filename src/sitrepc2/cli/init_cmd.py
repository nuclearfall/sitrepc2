# src/sitrepc2/cli/init_cmd.py
from __future__ import annotations

from pathlib import Path
import shutil

import typer

from sitrepc2.config.paths import (
    find_repo_root,
    get_dotpath,
    reference_root,
    source_gazetteer_paths,
    source_lexicon_path,
)
app = typer.Typer()


@app.command()
def init(path: Path = Path(".")):
    project_root = path.resolve()
    dot = project_dotpath(project_root)           # e.g. project_root / ".sitrepc2"
    dot.mkdir(parents=True, exist_ok=True)

    src_root = reference_root()
    # Copy tree (ignoring __pycache__ etc. if you ever have any)
    for src in src_root.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(src_root)
        dst = dot / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
