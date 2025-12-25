# src/sitrepc2/config/paths.py
from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOTDIR_NAME = ".sitrepc2"
SOURCE_DIR = "sitrepc2"

# Seed filenames (packaged)
SEED_GAZETTEER_DB = "seed_gazetteer.db"
SEED_LEXICON = "seed_lexicon.json"
SEED_SOURCES = "seed_sources.jsonl"

# Workspace filenames
GAZETTEER_DB = "gazetteer.db"
RECORDS_DB = "records.db"
LEXICON = "lexicon.json"
SOURCES = "sources.jsonl"

# Schema filenames
REC_SCHEMA_INGEST = "ingest.sql"
REC_SCHEMA_LSS = "lss.sql"
GAZ_SCHEMA_GAZETTEER = "gazetteer.sql"

# ---------------------------------------------------------------------------
# Repo / workspace discovery
# ---------------------------------------------------------------------------

def find_repo_root(start: Optional[Path] = None) -> Path:
    """
    Locate the project root by walking upward until a `.sitrepc2/` directory
    is found. Used ONLY after initialization.
    """
    start = start or Path.cwd()
    p = start.resolve()

    for parent in [p] + list(p.parents):
        if (parent / DOTDIR_NAME).is_dir():
            return parent

    raise RuntimeError(
        f"No {DOTDIR_NAME}/ directory found upward from {start}. "
        "Run `sitrepc2 init` first."
    )

def dot_path(root: Optional[Path] = None) -> Path:
    """
    Return the workspace path. During init, `root` must be supplied.
    """
    if root is not None:
        return root / DOTDIR_NAME
    return find_repo_root() / DOTDIR_NAME

# ---------------------------------------------------------------------------
# Packaged reference paths
# ---------------------------------------------------------------------------

def seed_reference_path() -> Path:
    return Path(files(SOURCE_DIR) / "reference")

def schema_root_path() -> Path:
    return Path(files(SOURCE_DIR) / "schema")

def rec_schema_root_path() -> Path:
    return schema_root_path() / "records"

def gaz_schema_root_path() -> Path:
    return schema_root_path() / "gazetteer"

# ---------------------------------------------------------------------------
# Seed files
# ---------------------------------------------------------------------------

def seed_lexicon_path() -> Path:
    return seed_reference_path() / SEED_LEXICON

def seed_sources_path() -> Path:
    return seed_reference_path() / SEED_SOURCES

def seed_gazetteer_path() -> Path:
    return seed_reference_path() / SEED_GAZETTEER_DB

# ---------------------------------------------------------------------------
# Workspace files
# ---------------------------------------------------------------------------

def gazetteer_path(root: Optional[Path] = None) -> Path:
    return dot_path(root) / GAZETTEER_DB

def records_path(root: Optional[Path] = None) -> Path:
    return dot_path(root) / RECORDS_DB

def lexicon_path(root: Optional[Path] = None) -> Path:
    return dot_path(root) / LEXICON

def sources_path(root: Optional[Path] = None) -> Path:
    return dot_path(root) / SOURCES

# ---------------------------------------------------------------------------
# Schema files
# ---------------------------------------------------------------------------

def ingest_schema_path() -> Path:
    return rec_schema_root_path() / REC_SCHEMA_INGEST

def lss_schema_path() -> Path:
    return rec_schema_root_path() / REC_SCHEMA_LSS

def gazetteer_schema_path() -> Path:
    return gaz_schema_root_path() / GAZ_SCHEMA_GAZETTEER
