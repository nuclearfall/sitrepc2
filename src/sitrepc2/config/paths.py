# src/sitrepc2/config/paths.py
from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Optional, Tuple
from importlib.resources import files


# ---------------------------------------------------------------------------
# 1. Detect project root (git-style)
# ---------------------------------------------------------------------------

DOTDIR_NAME = ".sitrepc2"
SEED_DB_NAME = "sitrepc2_seed.db"

def find_repo_root(start: Optional[Path] = None) -> Path:
    """
    Locate the project root by walking upward until a `.sitrepc2/` directory
    is found. This matches the original sitrepc2 workspace initialization model.
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


def get_dotpath(root: Path) -> Path:
    return root / DOTDIR_NAME


def dot_path(root: Path, path: str | Path) -> Path:
    return get_dotpath(root) / path


# ---------------------------------------------------------------------------
# 2. Database paths (new primary persistence layer)
# ---------------------------------------------------------------------------

DB_NAME = "sitrepc2.db"

def db_path(root: Path) -> Path:
    """Return the SQLite database path inside `.sitrepc2/`."""
    return dot_path(root, DB_NAME)


def current_db_path() -> Path:
    """Convenience wrapper: SQLite database for the current project."""
    return db_path(find_repo_root())

def seed_db_path() -> Path:
    return Path(files("sitrepc2") / "reference" / SEED_DB_NAME)

# ---------------------------------------------------------------------------
# 3. Workspace paths still relevant (lexicon, tg sources)
# ---------------------------------------------------------------------------

LEX_JSON = "war_lexicon.json"
TGM_SOURCES = "tg_channels.jsonl"


def lexicon_path(root: Path) -> Path:
    return dot_path(root, LEX_JSON)


def tg_channels_path(root: Path) -> Path:
    return dot_path(root, TGM_SOURCES)


# ---------------------------------------------------------------------------
# 4. Canonical reference files (still used for seeding DB)
# ---------------------------------------------------------------------------

def reference_root() -> Path:
    """Directory containing canonical reference data inside the package."""
    return Path(files("sitrepc2") / "reference")


def ref_path(path: str | Path) -> Path:
    return reference_root() / path


# -- Canonical CSVs (optional, used mostly for import scripts) --

GAZ_LOCALE = "locale_lookup.csv"
GAZ_REGION = "region_lookup.csv"
GAZ_GROUPS = "group_lookup.csv"
GAZ_DIRECTIONS = "direction_lookup.csv"

# Retain these ONLY as source materials for DB seeding
GAZ_PATHS = (GAZ_LOCALE, GAZ_REGION, GAZ_GROUPS, GAZ_DIRECTIONS)


def source_gazetteer_paths() -> Tuple[Path, Path, Path]:
    """Return the canonical CSV paths *shipped with the package*."""
    return tuple(ref_path(gaz) for gaz in GAZ_PATHS)


def source_op_groups_path() -> Path:
    return ref_path(GAZ_GROUPS)


def source_tg_channels_path() -> Path:
    return ref_path(TGM_SOURCES)


def source_lexicon_path() -> Path:
    return ref_path(LEX_JSON)


# ---------------------------------------------------------------------------
# 5. Current workspace discovery helpers
# ---------------------------------------------------------------------------

def current_root() -> Path:
    return find_repo_root()


def current_dotpath() -> Path:
    return get_dotpath(current_root())


# This previously surfaced CSV workspace copies — now removed.
# SQLite is the primary persistence layer, so CSV material does not appear here.
#
# def current_gazetteer() -> Tuple[Path, ...]:
#     return tuple(current_dotpath() / gaz for gaz in GAZ_PATHS)
def source_region_lookup_path() -> Path:
    return ref_path(GAZ_REGION)


def source_group_lookup_path() -> Path:
    return ref_path(GAZ_GROUPS)


def source_locale_lookup_path() -> Path:
    return ref_path(GAZ_LOCALE)


def source_direction_lookup_path() -> Path:
    return ref_path(GAZ_DIRECTIONS)

