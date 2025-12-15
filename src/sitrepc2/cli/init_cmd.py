from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

import typer

from sitrepc2.config.paths import (
    get_dotpath,
    db_path,
    reference_root,
)

# NOTE: invoke_without_command=True lets `sitrepc2 init` run directly
app = typer.Typer(
    help="Initialize a sitrepc2 workspace.",
    invoke_without_command=True,
)


# ----------------------------------------------------------------------
# NLP helper functions
# ----------------------------------------------------------------------

def _spacy_model_installed(model: str) -> bool:
    try:
        import spacy
        spacy.load(model)
        return True
    except Exception:
        return False


def _install_spacy_model(model: str) -> None:
    typer.secho(f"Installing spaCy model: {model}", fg=typer.colors.CYAN)
    subprocess.check_call(
        [sys.executable, "-m", "spacy", "download", model]
    )


def _coreferee_installed() -> bool:
    try:
        import spacy
        import coreferee

        nlp = spacy.load("en_core_web_lg")
        if "coreferee" not in nlp.pipe_names:
            nlp.add_pipe("coreferee")

        doc = nlp("Alice said she was tired.")
        return hasattr(doc._, "coref_chains")
    except Exception:
        return False


def _install_coreferee() -> None:
    typer.secho("Installing Coreferee language data (en)", fg=typer.colors.CYAN)
    subprocess.check_call(
        [sys.executable, "-m", "coreferee", "install", "en"]
    )


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
):
    """
    Initialize a sitrepc2 workspace at PATH.

    This will:
      • create a `.sitrepc2/` directory if it does not exist
      • copy the packaged seed database into `.sitrepc2/sitrepc2.db` if missing
      • copy reference files (lexicon, tg channels) if missing
      • ensure required spaCy and Coreferee models are installed
    """
    if ctx.invoked_subcommand is not None:
        return

    project_root = path.resolve()
    dot = get_dotpath(project_root)
    dot.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Copy seed database from packaged reference
    # ------------------------------------------------------------------
    dst_db = db_path(project_root)
    if dst_db.exists():
        typer.secho(f"Database already exists: {dst_db}", fg=typer.colors.YELLOW)
    else:
        src_db = reference_root() / "sitrepc2_seed.db"
        if not src_db.exists():
            raise RuntimeError(
                f"Seed database not found at {src_db}. "
                "Expected it to be packaged under src/sitrepc2/reference/."
            )

        dst_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_db, dst_db)
        typer.secho(
            f"Copied seed DB: {src_db.name} → {dst_db}",
            fg=typer.colors.GREEN,
        )

    # ------------------------------------------------------------------
    # 2. Copy reference files (if missing)
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

    # ------------------------------------------------------------------
    # 3. Ensure NLP runtime assets
    # ------------------------------------------------------------------
    typer.secho("Checking NLP runtime assets…", fg=typer.colors.CYAN)

    try:
        import spacy  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "spaCy is not installed. Run `pip install -e .` first."
        ) from e

    try:
        import coreferee  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "coreferee is not installed. Run `pip install -e .` first."
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
