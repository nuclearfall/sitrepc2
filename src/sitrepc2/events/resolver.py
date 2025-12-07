# src/sitrepc2/locations/resolver.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sitrepc2.locations.event_locations import EventLocation
from sitrepc2.gazetteer.types import LocaleCandidate  # whatever you already use


@dataclass(frozen=True, slots=True)
class ResolvedEventLocation:
    loc: EventLocation
    candidates: list[LocaleCandidate]
    decision: str      # "auto" | "ambiguous" | "unresolved"
    confidence: float  # 0.0–1.0


class LocationResolver:
    def resolve_event_locations(
        self,
        event_locs: Sequence[EventLocation],
    ) -> list[ResolvedEventLocation]:
        results: list[ResolvedEventLocation] = []

        for loc in event_locs:
            # Plug into your existing resolver / gazetteer engine here
            # using loc.base_name, loc.event context, frontline, etc.
            candidates, decision, confidence = self._resolve_one(loc)

            results.append(
                ResolvedEventLocation(
                    loc=loc,
                    candidates=candidates,
                    decision=decision,
                    confidence=confidence,
                )
            )

        return results

    def _resolve_one(
        self,
        loc: EventLocation,
    ) -> tuple[list[LocaleCandidate], str, float]:
        # Placeholder: integrate your real scoring / region/ru_group/frontline logic.
        return [], "unresolved", 0.0
