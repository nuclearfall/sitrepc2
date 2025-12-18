# src/sitrepc2/cli/init_cmd.py
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import sqlite3

import typer

from sitrepc2.config.paths import (
    get_dotpath,
    db_path,                # gazetteer.db (lookup DB)
    reference_root,
    schema_root,            # schemas/
    records_db_path,        # records.db (authoritative pipeline DB)
)

# NOTE: invoke_without_command=True lets `sitrepc2 init` run directly
app = typer.Typer(
    help="Initialize a sitrepc2 workspace.",
    invoke_without_command=True,
)

# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------
def _apply_all_schemas(db_path: Path, schema_dir: Path) -> None:
    """
    Apply all SQL schema files in schema_dir to db_path.

    Schemas are applied in lexicographic order to ensure
    dependency safety (ingest → lss → dom → review).
    """
    if not schema_dir.exists() or not schema_dir.is_dir():
        raise RuntimeError(f"Schema directory not found: {schema_dir}")

    sql_files = sorted(schema_dir.glob("*.sql"))
    if not sql_files:
        raise RuntimeError(f"No .sql schema files found in {schema_dir}")

    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON;")
        for sql_file in sql_files:
            typer.secho(
                f"Applying schema: {sql_file.name}",
                fg=typer.colors.CYAN,
            )
            con.executescript(sql_file.read_text(encoding="utf-8"))

def _apply_sql(db_path: Path, sql_path: Path) -> None:
    if not sql_path.exists():
        raise RuntimeError(f"Schema file not found: {sql_path}")

    with sqlite3.connect(db_path) as con:
        con.execute("PRAGMA foreign_keys = ON;")
        con.executescript(sql_path.read_text(encoding="utf-8"))


def _init_records_db(dot: Path) -> Path:
    """
    Create and initialize the authoritative records.db
    using all packaged SQL schemas.
    """
    records_db = records_db_path(dot.parent)
    records_db.parent.mkdir(parents=True, exist_ok=True)

    if not records_db.exists():
        records_db.touch()
        typer.secho(
            f"Created records database: {records_db}",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"Records database already exists: {records_db}",
            fg=typer.colors.YELLOW,
        )

    schema_dir = schema_root()
    _apply_all_schemas(records_db, schema_dir)

    return records_db



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
        import coreferee  # noqa: F401

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
    path: Path = typer.Argument(
        Path("."),
        help="Project root to initialize (default: current directory).",
    ),
    reconfigure: bool = typer.Option(
        False,
        "--reconfigure",
        help="Remove existing .sitrepc2 workspace and reinitialize from scratch.",
    ),
):
    """
    Initialize a sitrepc2 workspace at PATH.

    This will:
      • create a `.sitrepc2/` directory if missing
      • copy the packaged lookup seed DB (`gazetteer.db`) if missing
      • create and initialize `records.db`
      • copy reference files if missing
      • ensure required spaCy and Coreferee models are installed
    """
    if ctx.invoked_subcommand is not None:
        return

    project_root = path.resolve()
    dot = get_dotpath(project_root)

    if reconfigure and dot.exists():
        typer.secho(
            f"Reconfiguring workspace: removing {dot}",
            fg=typer.colors.RED,
            bold=True,
        )
        shutil.rmtree(dot)
        
    dot.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Copy lookup seed database (gazetteer.db)
    # ------------------------------------------------------------------
    lookup_db = db_path(project_root)
    if lookup_db.exists():
        typer.secho(
            f"Lookup database already exists: {lookup_db}",
            fg=typer.colors.YELLOW,
        )
    else:
        src_db = reference_root() / "gazetteer_seed.db"
        if not src_db.exists():
            raise RuntimeError(
                f"Seed database not found at {src_db}. "
                "Expected it under src/sitrepc2/reference/."
            )

        lookup_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_db, lookup_db)
        typer.secho(
            f"Copied lookup DB: {src_db.name} → {lookup_db}",
            fg=typer.colors.GREEN,
        )

    # ------------------------------------------------------------------
    # 2. Initialize records.db (authoritative pipeline DB)
    # ------------------------------------------------------------------
    _init_records_db(dot)

    # ------------------------------------------------------------------
    # 3. Copy reference files into workspace (if missing)
    # ------------------------------------------------------------------

        # War lexicon (authoritative runtime copy)
    lex_src = reference_root() / "war_lexicon.json"
    lex_dst = dot / "war_lexicon.json"

    if lex_src.exists() and not lex_dst.exists():
        shutil.copy2(lex_src, lex_dst)
        typer.secho(
            "Copied war_lexicon.json into workspace.",
            fg=typer.colors.GREEN,
        )

    # Telegram sources (optional runtime config)
    tg_src = reference_root() / "tg_channels.jsonl"
    tg_dst = dot / "tg_channels.jsonl"

    if tg_src.exists() and not tg_dst.exists():
        shutil.copy2(tg_src, tg_dst)
        typer.secho(
            "Copied tg_channels.jsonl into workspace.",
            fg=typer.colors.GREEN,
        )

    # ------------------------------------------------------------------
    # 4. Ensure NLP runtime assets
    # ------------------------------------------------------------------
    typer.secho("Checking NLP runtime assets…", fg=typer.colors.CYAN)

    try:
        import spacy  # noqa: F401
        import coreferee  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "spaCy and coreferee must be installed. Run `pip install -e .`."
        ) from e

    if not _spacy_model_installed("en_core_web_lg"):
        _install_spacy_model("en_core_web_lg")
    else:
        typer.secho(
            "spaCy model en_core_web_lg already installed.",
            fg=typer.colors.GREEN,
        )

    if not _coreferee_installed():
        _install_coreferee()
    else:
        typer.secho(
            "Coreferee already installed and functional.",
            fg=typer.colors.GREEN,
        )

    typer.secho("Workspace initialized.", fg=typer.colors.CYAN)
