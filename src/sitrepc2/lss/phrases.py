# src/sitrepc2/lss/phrases.py
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import holmes_extractor as holmes

from sitrepc2.config.paths import lexicon_path as lexicon_db_path


def load_war_lexicon() -> dict[str, Any]:
    import json
    path = lexicon_db_path()
    if not path or not path.exists():
        raise FileNotFoundError(
            "Unable to locate war_lexicon.json. Have you run 'sitrepc2 init'?"
        )
    with path.open("r", encoding="utf8") as f:
        return json.load(f)


def _norm_trigger(s: str) -> str:
    return s.strip().lower()


def _iter_triggers(values: Iterable[str]) -> Iterable[str]:
    seen: set[str] = set()
    for raw in values:
        trigger = _norm_trigger(raw)
        if not trigger or trigger in seen:
            continue
        seen.add(trigger)
        yield trigger


def register_search_phrases(manager: holmes.Manager) -> None:
    """
    Register Holmes search phrases.

    Contract:
    - Emits EventMatch only
    - No location logic
    - No context logic
    - No role inference
    """

    lexicon = load_war_lexicon()

    actions = lexicon["actions"]
    outcomes = lexicon["outcomes"]
    casualties = lexicon.get("casualties", {})
    air_defence = lexicon.get("air_defence", {})
    missile_troops = lexicon.get("missile_troops", {})

    reg = manager.register_search_phrase

    for verb in _iter_triggers(actions["kinetic_verbs"]):
        reg(f"Somebody {verb} something", label="KINETIC_EVENT")

    for verb in _iter_triggers(actions["maneuver_verbs"]):
        reg(f"Somebody {verb} something", label="MANEUVER_EVENT")

    for verb in _iter_triggers(actions["defensive_verbs"]):
        reg(f"Somebody {verb} something", label="DEFENSIVE_EVENT")

    for verb in _iter_triggers(actions["interdiction_verbs"]):
        reg(f"Somebody {verb} something", label="INTERDICTION_EVENT")

    for verb in _iter_triggers(actions["support_verbs"]):
        reg(f"Somebody {verb} something", label="SUPPORT_EVENT")

    for core in _iter_triggers(actions["action_phrases"]):
        reg(f"Somebody {core} in something", label="ACTION_PHRASE_EVENT")

    for verb in _iter_triggers(outcomes["outcome_verbs"]):
        reg(f"Somebody {verb} something", label="OUTCOME_EVENT")

    for noun in _iter_triggers(outcomes["outcome_nouns"]):
        reg(f"{noun} in something", label="OUTCOME_EVENT")

    for core in _iter_triggers(outcomes["outcome_phrases"]):
        reg(f"Somebody {core} in something", label="OUTCOME_EVENT")

    for verb in _iter_triggers(casualties.get("casualty_verbs", [])):
        reg(f"Somebody {verb} somebody", label="CASUALTY_EVENT")

    for noun in _iter_triggers(casualties.get("casualty_nouns", [])):
        reg(f"{noun} among somebody", label="CASUALTY_EVENT")

    for core in _iter_triggers(casualties.get("casualty_phrases", [])):
        reg(f"Somebody {core} near something", label="CASUALTY_EVENT")

    for verb in _iter_triggers(air_defence.get("air_defence_verbs", [])):
        reg(f"Air defence units {verb} something", label="AIR_DEFENCE_EVENT")

    for core in _iter_triggers(air_defence.get("air_defence_phrases", [])):
        reg(f"Somebody {core} over something", label="AIR_DEFENCE_EVENT")

    for verb in _iter_triggers(missile_troops.get("missile_verbs", [])):
        reg(f"Missile troops {verb} something", label="MISSILE_EVENT")

    for core in _iter_triggers(missile_troops.get("missile_phrases", [])):
        reg(f"Somebody {core} on something", label="MISSILE_EVENT")
