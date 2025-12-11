# src/sitrepc2/config/paths.py
from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# 1. Detect project root (git-style)
# ---------------------------------------------------------------------------

DOTDIR_NAME = ".sitrepc2"


def find_repo_root(start: Optional[Path] = None) -> Path:
    """
    Starting from `start` (or cwd), walk upward until a `.sitrepc2` directory
    is found. Return that directory's parent as the repo root.

    If none is found, raise an error — the user must run `sitrepc2 init`.
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
    """Return the `.sitrepc2` directory for the given project root."""
    return root / DOTDIR_NAME

def dot_path(root: Path, path: str | Path) -> Path:
    """Return a path inside the project's `.sitrepc2/` directory."""
    return get_dotpath(root) / path


# ---------------------------------------------------------------------------
# 2. Workspace paths (mutable copies in .sitrepc2/)
# ---------------------------------------------------------------------------

GAZ_LOCALE = "locale_lookup.csv"
GAZ_REGION = "region_lookup.csv"
GAZ_GROUPS = "group_lookup.csv"
# GAZ_FEATURES = "features_expanded.csv"
LEX_JSON = "war_lexicon.json"
TGM_SOURCES = "tg_channels.jsonl"
GAZ_PATHS = (
    GAZ_LOCALE,
    GAZ_REGION,
    GAZ_GROUPS,
)


def op_groups_path(root: Path) -> Path:
    """Return workspace operational group AO path in `.sitrepc2/`."""
    return dot_path(root, GAZ_GROUPS)

def lexicon_path(root: Path) -> Path:
    """Return workspace lexicon path in `.sitrepc2/`."""
    return dot_path(root, LEX_JSON)

def tg_channels_path(root: Path) -> Path:
    """Return workspace Telegram channel list path in `.sitrepc2/`."""
    return dot_path(root, TGM_SOURCES)

# ---------------------------------------------------------------------------
# 3. Canonical reference files (read-only inside installed package)
# ---------------------------------------------------------------------------

def reference_root() -> Path:
    """
    Returns the directory containing the canonical reference data shipped
    inside the installed sitrepc2 package.
    """
    return Path(files("sitrepc2") / "reference")


def ref_path(path: str | Path) -> Path:
    return reference_root() / path


def source_gazetteer_paths() -> Tuple[Path, Path, Path]:
    """Return canonical gazetteer paths inside the installed package."""
    return tuple(ref_path(gaz) for gaz in GAZ_PATHS)

def source_op_groups_path() -> Path:
    return ref_path(GAZ_GROUPS)

def source_tg_channels_path() -> Path:
    return ref_path(TGM_SOURCES)

def source_lexicon_path() -> Path:
    """Return canonical lexicon path inside the installed package."""
    return ref_path(LEX_JSON)


def current_root() -> Path:
    """Discover the current sitrepc2 project root (git-style)."""
    return find_repo_root()

def current_dotpath() -> Path:
    """Return the `.sitrepc2` path for the current working project."""
    return get_dotpath(current_root())

def current_gazetteer() -> Tuple[Path, ...]:
    return tuple(current_dotpath() / gaz for gaz in GAZ_PATHS)
