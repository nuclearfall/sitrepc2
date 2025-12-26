# src/sitrepc2/cli/init_cmd.py
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import sqlite3

import typer

from sitrepc2.config.paths import (
    dot_path,
    seed_lexicon_path,
    seed_sources_path,
    seed_gazetteer_path,
    gazetteer_path,
    records_path,
    lexicon_path,
    sources_path,
    rec_schema_root_path,
)

app = typer.Typer(
    help="Initialize a sitrepc2 workspace.",
    invoke_without_command=True,
)

# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _apply_rec_schemas(db_path: Path) -> None:
    schema_dir = rec_schema_root_path()

    if not schema_dir.exists():
        raise RuntimeError(f"Schema directory not found: {schema_dir}")

    sql_files = sorted(schema_dir.glob("*.sql"))
    if not sql_files:
        raise RuntimeError(f"No .sql files found in {schema_dir}")

    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON;")
        for sql in sql_files:
            typer.secho(f"Applying schema: {sql.name}", fg=typer.colors.CYAN)
            con.executescript(sql.read_text(encoding="utf-8"))

def _init_records_db(root: Path) -> None:
    db = records_path(root)
    db.parent.mkdir(parents=True, exist_ok=True)

    is_new = not db.exists()

    if is_new:
        db.touch()
        typer.secho(f"Created records database: {db}", fg=typer.colors.GREEN)
        _apply_rec_schemas(db)
    else:
        typer.secho(f"Records database exists: {db}", fg=typer.colors.YELLOW)

def _spacy_model_installed(model: str) -> bool:
    try:
        import spacy
        spacy.load(model)
        return True
    except Exception:
        return False

def _install_spacy_model(model: str) -> None:
    typer.secho(f"Installing spaCy model: {model}", fg=typer.colors.CYAN)
    subprocess.check_call([sys.executable, "-m", "spacy", "download", model])

def _coreferee_installed() -> bool:
    try:
        import spacy
        import coreferee  # noqa

        nlp = spacy.load("en_core_web_lg")
        if "coreferee" not in nlp.pipe_names:
            nlp.add_pipe("coreferee")

        doc = nlp("Alice said she was tired.")
        return hasattr(doc._, "coref_chains")
    except Exception:
        return False

def _install_coreferee() -> None:
    typer.secho("Installing Coreferee language data (en)", fg=typer.colors.CYAN)
    subprocess.check_call([sys.executable, "-m", "coreferee", "install", "en"])

# ----------------------------------------------------------------------
# init command
# ----------------------------------------------------------------------

@app.callback()
def init(
    ctx: typer.Context,
    reconfigure: bool = typer.Option(
        False,
        "--reconfigure",
        help="Remove existing .sitrepc2 workspace and reinitialize.",
    ),
):
    if ctx.invoked_subcommand is not None:
        return

    init_workspace(reconfigure=reconfigure)


def init_workspace(
    *,
    root: Path | None = None,
    reconfigure: bool = False,
) -> None:
    """
    Initialize a sitrepc2 workspace.

    Safe to call multiple times.
    Raises on failure.
    """
    root = root or Path.cwd()
    dot = dot_path(root)

    if reconfigure and dot.exists():
        typer.secho(f"Removing workspace: {dot}", fg=typer.colors.RED, bold=True)
        shutil.rmtree(dot)

    dot.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------
    # 1. Gazetteer DB
    # --------------------------------------------------
    gz_dst = gazetteer_path(root)
    if gz_dst.exists():
        typer.secho(f"Gazetteer DB exists: {gz_dst}", fg=typer.colors.YELLOW)
    else:
        src = seed_gazetteer_path()
        if not src.exists():
            raise RuntimeError(f"Missing seed DB: {src}")
        shutil.copy2(src, gz_dst)
        typer.secho("Seeded gazetteer DB.", fg=typer.colors.GREEN)

    # --------------------------------------------------
    # 2. Records DB
    # --------------------------------------------------
    _init_records_db(root)

    # --------------------------------------------------
    # 3. Lexicon DB (reference)
    # --------------------------------------------------
    lx_dst = lexicon_path(root)
    if lx_dst.exists():
        typer.secho(f"Lexicon DB exists: {lx_dst}", fg=typer.colors.YELLOW)
    else:
        src = seed_lexicon_path()
        if not src.exists():
            raise RuntimeError(f"Missing seed DB: {src}")
        shutil.copy2(src, lx_dst)
        typer.secho("Seeded lexicon DB.", fg=typer.colors.GREEN)

    # --------------------------------------------------
    # 4. Copy Sources
    # --------------------------------------------------

    if not sources_path(root).exists():
        shutil.copy2(seed_sources_path(), sources_path(root))
        typer.secho("Seeded .sitrepc2/sources.jsonl", fg=typer.colors.GREEN)

    # --------------------------------------------------
    # 5. NLP runtime
    # --------------------------------------------------
    typer.secho("Checking NLP runtime…", fg=typer.colors.CYAN)

    try:
        import spacy  # noqa
        import coreferee  # noqa
    except ImportError as e:
        raise RuntimeError(
            "spaCy and coreferee must be installed first."
        ) from e

    if not _spacy_model_installed("en_core_web_lg"):
        _install_spacy_model("en_core_web_lg")
    else:
        typer.secho("spaCy model installed.", fg=typer.colors.GREEN)

    if not _coreferee_installed():
        _install_coreferee()
    else:
        typer.secho("Coreferee functional.", fg=typer.colors.GREEN)

    typer.secho("Workspace initialized.", fg=typer.colors.CYAN)