# src/sitrepc2/locations/event_locations.py  (continued)
from typing import Iterable, Sequence

from spacy.tokens import Doc, Span

LOCATION_ENTS = {"GPE", "LOC", "FAC"}


class EventLocationExtractor:
    """
    Given Events and a Doc, extract location mentions *scoped to* each event.
    """

    def extract_for_events(
        self,
        events: Sequence[Event],
        doc: Doc,
    ) -> list[EventLocation]:
        results: list[EventLocation] = []

        for event in events:
            sent: Span = event.span.sent

            for ent in sent.ents:
                if ent.label_ not in LOCATION_ENTS:
                    continue

                base_name = self._extract_base_toponym(ent)
                if not base_name:
                    continue

                results.append(
                    EventLocation(
                        event=event,
                        span=ent,
                        base_name=base_name,
                        source="ent",
                    )
                )

        return results

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _extract_base_toponym(self, ent: Span) -> str | None:
        """
        For spans like:
          - "Kupyansk direction"
          - "Sloviansk area"
          - "Donetsk region"
        return the core toponym ("Kupyansk", "Sloviansk", "Donetsk").

        For plain names ("Kupyansk", "Avdiivka"), just return ent.text.
        """

        text = ent.text.strip()

        # very simple heuristic for now; you can expand with UA/RU patterns:
        lowered = text.lower()
        tail_words = (" direction", " area", " region", " district", " line")

        for tail in tail_words:
            if lowered.endswith(tail):
                # strip tail by length to preserve original casing
                core = text[: len(text) - len(tail)]
                return core.strip() or None

        return text or None
