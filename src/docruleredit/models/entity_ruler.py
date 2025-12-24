from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Dict, Any
import uuid


@dataclass(slots=True)
class EntityRulerModel:
    """
    Pure data model representing a user-defined EntityRuler rule.

    This model is intentionally independent of:
    - spaCy Language / EntityRuler components
    - GUI widgets

    It can be safely serialized to and from JSONL.
    """

    # Stable identifier for persistence and UI selection
    ruler_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    # Human-readable name (shown in UI)
    name: str = ""

    # spaCy entity label (ent_type)
    label: str = ""

    # Raw text patterns provided by the user (pre-split)
    patterns: List[str] = field(default_factory=list)

    # Whether matching should normalize text using .lower()
    normalize: bool = True

    # Highlight color (hex string, e.g. "#ffcc00")
    color: str = "#ffd966"

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_json(self) -> Dict[str, Any]:
        """
        Convert this ruler to a JSON-serializable dict.

        This representation is stable and version-agnostic.
        """
        return {
            "ruler_id": self.ruler_id,
            "name": self.name,
            "label": self.label,
            "patterns": list(self.patterns),
            "normalize": self.normalize,
            "color": self.color,
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "EntityRulerModel":
        """
        Create an EntityRulerModel from a JSON dict.

        Unknown keys are ignored to allow forward compatibility.
        """
        return cls(
            ruler_id=data.get("ruler_id", uuid.uuid4().hex),
            name=data.get("name", ""),
            label=data.get("label", ""),
            patterns=list(data.get("patterns", [])),
            normalize=bool(data.get("normalize", True)),
            color=data.get("color", "#ffd966"),
        )

    # ------------------------------------------------------------------
    # Pattern helpers
    # ------------------------------------------------------------------

    def iter_patterns(self) -> Iterable[str]:
        """
        Yield patterns, applying normalization if required.
        """
        if self.normalize:
            for p in self.patterns:
                yield p.lower()
        else:
            yield from self.patterns
