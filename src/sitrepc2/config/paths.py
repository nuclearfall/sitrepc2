# src/sitrepc2/config/paths.py
from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Optional, Dict


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


# ---------------------------------------------------------------------------
# 2. Workspace paths (mutable copies in .sitrepc2/)
# ---------------------------------------------------------------------------

GAZ_LOCALE = "locale_lookup.csv"
GAZ_REGION = "region_lookup.csv"
GAZ_OPGROUP = "op_groups_ao.geojson"
GAZ_FEATURES = "features_expanded.csv"
LEX_JSON = "war_lexicon.json"


def gazetteer_paths(dotpath: Path) -> Dict[str, Path]:
    """Return workspace gazetteer paths in `.sitrepc2/`."""
    return {
        "locale": dotpath / GAZ_LOCALE,
        "region": dotpath / GAZ_REGION,
    }


def get_lexicon(dotpath: Path) -> Path:
    """Return the workspace lexicon path in `.sitrepc2/`."""
    return dotpath / LEX_JSON


# ---------------------------------------------------------------------------
# 3. Canonical reference files (read-only inside installed package)
# ---------------------------------------------------------------------------

def reference_root() -> Path:
    """
    Returns the directory containing the canonical reference data shipped
    inside the installed sitrepc2 package.
    """
    return Path(files("sitrepc2") / "reference")


def source_gazetteer_paths() -> Dict[str, Path]:
    """Return canonical gazetteer paths inside the installed package."""
    base = reference_root() / "gazetteer"
    return {
        "locale": base / GAZ_LOCALE,
        "region": base / GAZ_REGION,
    }


def source_lexicon_path() -> Path:
    """Return canonical lexicon path inside the installed package."""
    return reference_root() / LEX_JSON
