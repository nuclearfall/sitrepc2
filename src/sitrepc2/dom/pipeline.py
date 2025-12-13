# src/sitrepc2/dom/pipeline.py

from __future__ import annotations
from typing import Iterable, Dict, Optional

from sitrepc2.dom.input_typedefs import (
    DOMPostInput,
    DOMSectionInput,
    DOMEventClaimInput,
)

from sitrepc2.dom.output_typedefs import (
    ResolvedPost,
    ResolvedSection,
    ResolvedEvent,
)

from sitrepc2.gazetteer.index import GazetteerIndex
from sitrepc2.spatial.frontline import Frontline

# Existing DOM helpers (already implemented)
from sitrepc2.dom.resolution import (
    apply_region_context_to_event,
    apply_group_context_to_event,
    apply_direction_context_to_event,
    compute_frontline_distances,
    perform_candidate_clustering,
)


class DOMProcessor:
    """
    Deterministic, phase-ordered DOM processor.
    """

    def __init__(
        self,
        gazetteer: GazetteerIndex,
        frontline: Optional[Frontline] = None,
    ):
        self.gaz = gazetteer
        self.frontline = frontline

    # ==========================================================
    # PUBLIC ENTRY POINT
    # ==========================================================

    def process_posts(
        self,
        posts: Iterable[DOMPostInput],
    ) -> list[ResolvedPost]:
        return [self.process_post(post) for post in posts]

    def process_post(self, post: DOMPostInput) -> ResolvedPost:
        # PHASE 1 — Resolve post-level context
        post_ctx = self._resolve_contexts(post.contexts)

        resolved_sections: list[ResolvedSection] = []

        for section in post.sections:
            resolved_sections.append(
                self._process_section(section, post_ctx)
            )

        return ResolvedPost(
            post_id=post.post_id,
            source=post.source,
            channel=post.channel,
            published_at=post.published_at,
            sections=resolved_sections,
        )

    # ==========================================================
    # SECTION PROCESSING
    # ==========================================================

    def _process_section(
        self,
        section: DOMSectionInput,
        inherited_ctx: Dict,
    ) -> ResolvedSection:
        section_ctx = self._merge_contexts(
            inherited_ctx,
            section.contexts,
        )

        resolved_events: list[ResolvedEvent] = []

        for claim in section.claims:
            resolved_events.append(
                self._process_event(claim, section_ctx, section.section_id)
            )

        return ResolvedSection(
            section_id=section.section_id,
            text=section.text,
            events=resolved_events,
        )

    # ==========================================================
    # EVENT PROCESSING (ALL DOM PHASES)
    # ==========================================================

    def _process_event(
        self,
        claim: DOMEventClaimInput,
        inherited_ctx: Dict,
        section_id: str,
    ) -> ResolvedEvent:
        # Merge claim-level contexts
        event_ctx = self._merge_contexts(
            inherited_ctx,
            claim.contexts,
        )

        # PHASE 2 — Candidate generation
        event = self._generate_location_candidates(claim)

        # PHASE 3 — Region narrowing (hard)
        apply_region_context_to_event(event, event_ctx.get("region"))

        # PHASE 4 — Group AO narrowing & proximity scoring
        apply_group_context_to_event(event, event_ctx.get("group"))

        # PHASE 5 — Direction / proximity anchor resolution
        apply_direction_context_to_event(
            event,
            event_ctx.get("direction"),
            self.frontline,
        )

        # PHASE 6 — Frontline distance scoring
        compute_frontline_distances(event, self.frontline)

        # PHASE 7 — Clustering & dominance
        perform_candidate_clustering(event)

        # PHASE 8 — Final materialization
        return self._materialize_resolved_event(
            event,
            claim,
            section_id,
        )

    # ==========================================================
    # CONTEXT HELPERS
    # ==========================================================

    def _resolve_contexts(self, contexts) -> Dict:
        """
        Convert DOMContextInput.text → Gazetteer entities.
        """
        out = {
            "region": None,
            "group": None,
            "direction": None,
            "proximity": None,
        }

        for ctx in contexts:
            if ctx.kind.value == "region":
                out["region"] = self.gaz.search_region(ctx.text)

            elif ctx.kind.value == "group":
                out["group"] = self.gaz.search_group(ctx.text)

            elif ctx.kind.value in ("direction", "proximity"):
                out[ctx.kind.value] = self.gaz.search_direction(ctx.text)

        return out

    def _merge_contexts(self, higher: Dict, local) -> Dict:
        out = dict(higher)
        for ctx in local:
            out.update(self._resolve_contexts([ctx]))
        return out
