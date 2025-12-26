# src/dbeditc2/enums.py
from __future__ import annotations

from enum import Enum, auto


class DatabaseKind(Enum):
    """
    High-level database selection.
    Used only for UI scoping and labeling.
    """
    GAZETTEER = auto()
    LEXICON = auto()


class CollectionKind(Enum):
    """
    Semantic collections exposed to the user.
    These deliberately do NOT map 1:1 to SQL tables.
    """

    # Gazetteer collections
    LOCATIONS = auto()
    REGIONS = auto()
    GROUPS = auto()
    DIRECTIONS = auto()

    # Lexicon collections
    EVENT_PHRASES = auto()
    CONTEXT_PHRASES = auto()


class EditorMode(Enum):
    """
    Current editor intent.
    Controls toolbar state and details panel behavior.
    """
    VIEW = auto()
    ADD = auto()
    EDIT = auto()
