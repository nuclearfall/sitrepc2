# src/sitrepc2/lss/rulers.py
from __future__ import annotations

from typing import List, Set, Tuple

from spacy.language import Language
from spacy.pipeline import EntityRuler

from sitrepc2.util.normalize import normalize_location_key
from sitrepc2.gazetteer.aliases import (
    gather_aliases,
    gather_aliases_from_db,
)
from sitrepc2.gazetteer.typedefs import (
    LocaleEntry,
    RegionEntry,
    GroupEntry,
    DirectionEntry,
)


# -----------------------------
# Helpers
# -----------------------------

def _simple_alias_patterns(aliases: Set[str], label: str) -> List[dict]:
    """
    Produce simple exact-match patterns (case-insensitive automatically in spaCy).
    Used for LOCALE, REGION, GROUP.

    aliases are already normalized strings (via normalize_location_key).
    """
    return [{"label": label, "pattern": alias} for alias in sorted(aliases)]


def _direction_phrase_patterns(aliases: Set[str]) -> List[dict]:
    """
    Produce LOWER-token patterns for directions for:
        - in the direction of X
        - towards X
        - X direction
        - X axis
        - X sector
        - the X line

    aliases are normalized strings (e.g. "avdiivka", not "Avdiivka direction").
    """
    patterns: List[dict] = []

    for alias in sorted(aliases):
        # alias is assumed already normalized, but be idempotent:
        norm = normalize_location_key(alias)

        # Token-based case-insensitive patterns
        patterns.extend(
            [
                # in the direction of X
                {
                    "label": "DIRECTION",
                    "pattern": [
                        {"LOWER": "in"},
                        {"LOWER": "the"},
                        {"LOWER": "direction"},
                        {"LOWER": "of"},
                        {"LOWER": norm},
                    ],
                },
                # towards X
                {
                    "label": "DIRECTION",
                    "pattern": [
                        {"LOWER": "towards"},
                        {"LOWER": norm},
                    ],
                },
                # X direction
                {
                    "label": "DIRECTION",
                    "pattern": [
                        {"LOWER": norm},
                        {"LOWER": "direction"},
                    ],
                },
                # X axis
                {
                    "label": "DIRECTION",
                    "pattern": [
                        {"LOWER": norm},
                        {"LOWER": "axis"},
                    ],
                },
                # X sector
                {
                    "label": "DIRECTION",
                    "pattern": [
                        {"LOWER": norm},
                        {"LOWER": "sector"},
                    ],
                },
                # the X line
                {
                    "label": "DIRECTION",
                    "pattern": [
                        {"LOWER": "the"},
                        {"LOWER": norm},
                        {"LOWER": "line"},
                    ],
                },
            ]
        )

    return patterns


def _ensure_entity_ruler(nlp: Language) -> EntityRuler:
    """
    Get or create the spaCy EntityRuler in a sensible position
    relative to `ner` if present.
    """
    if "entity_ruler" in nlp.pipe_names:
        ruler = nlp.get_pipe("entity_ruler")
    else:
        if "ner" in nlp.pipe_names:
            ruler = nlp.add_pipe("entity_ruler", before="ner")
        else:
            ruler = nlp.add_pipe("entity_ruler")

    assert isinstance(ruler, EntityRuler)
    ruler.validate = True
    ruler.ent_id_sep = None
    return ruler


def _install_patterns_from_alias_lists(
    nlp: Language,
    locale_aliases: List[str],
    region_aliases: List[str],
    group_aliases: List[str],
    direction_aliases: List[str],
) -> Language:
    """
    Core installer that takes precomputed alias lists and wires up the
    EntityRuler with LOCALE / REGION / GROUP / DIRECTION patterns.
    """
    ruler = _ensure_entity_ruler(nlp)

    # LOCALE / REGION / GROUP simple string patterns
    ruler.add_patterns(_simple_alias_patterns(set(locale_aliases), "LOCALE"))
    ruler.add_patterns(_simple_alias_patterns(set(region_aliases), "REGION"))
    ruler.add_patterns(_simple_alias_patterns(set(group_aliases), "GROUP"))

    # DIRECTION phrase patterns (token-based)
    ruler.add_patterns(_direction_phrase_patterns(set(direction_aliases)))

    return nlp


# -----------------------------
# Main entry points
# -----------------------------

def add_entity_rulers(
    nlp: Language,
    *,
    locales: List[LocaleEntry],
    regions: List[RegionEntry],
    groups: List[GroupEntry],
    directions: List[DirectionEntry],
) -> Language:
    """
    Install EntityRuler and populate it from in-memory gazetteer dataclasses:

        - locale aliases
        - region aliases
        - group aliases
        - direction aliases + direction phrase patterns

    This is the "dataclass-aware" entry point used when you already have
    LocaleEntry / RegionEntry / GroupEntry / DirectionEntry lists in memory
    (e.g. via GazetteerIndex.from_db()).
    """
    locale_aliases, region_aliases, group_aliases, direction_aliases = gather_aliases(
        locales, regions, groups, directions
    )

    return _install_patterns_from_alias_lists(
        nlp,
        locale_aliases=locale_aliases,
        region_aliases=region_aliases,
        group_aliases=group_aliases,
        direction_aliases=direction_aliases,
    )


def add_entity_rulers_from_db(nlp: Language) -> Language:
    """
    Convenience entry point: load all gazetteer aliases directly from the
    SQLite database (via gather_aliases_from_db) and install EntityRuler.

    This is useful when you don't need the dataclasses in the NLP layer and
    just want the gazetteer-backed patterns available in spaCy.
    """
    locale_aliases, region_aliases, group_aliases, direction_aliases = (
        gather_aliases_from_db()
    )

    return _install_patterns_from_alias_lists(
        nlp,
        locale_aliases=locale_aliases,
        region_aliases=region_aliases,
        group_aliases=group_aliases,
        direction_aliases=direction_aliases,
    )
