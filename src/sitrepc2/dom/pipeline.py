# src/sitrepc2/dom/pipeline.py

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Iterable, Dict

from sitrepc2.review.pd_nodes import (
    PDPost, PDSection, PDEvent, PDLocation
)

from sitrepc2.dom.resolution import (
    apply_region_context_to_event,
    apply_group_context_to_event,
    apply_direction_context_to_event,
    compute_frontline_distances,
    perform_candidate_clustering,
)

from sitrepc2.gazetteer.index import GazetteerIndex
from sitrepc2.spatial.frontline import Frontline
from sitrepc2.dom.typedefs import Location


# ===============================================================
# DOM ENTRY POINT
# ===============================================================

class DOMProcessor:
    """
    Runs full DOM-level enrichment and resolution on a reviewed PD tree.

    This class does NOT mutate structural layout of the PD tree.
    It ONLY enriches nodes by applying:
      - region / group narrowing
      - direction anchor resolution
      - frontline distance scoring
      - direction axis scoring
      - clustering assignment
      - final candidate selection
    """

    def __init__(self, gaz: GazetteerIndex, frontline: Optional[Frontline] = None):
        self.gaz = gaz
        self.frontline = frontline

    # ----------------------------------------------------------- #
    # PUBLIC API
    # ----------------------------------------------------------- #

    def process_posts(self, posts: Iterable[PDPost]) -> None:
        """
        Apply DOM processing to a batch of posts (in-place).
        """
        for post in posts:
            self.process_post(post)

    def process_post(self, post: PDPost) -> None:
        """
        Apply DOM logic to a single PDPost tree.
        """
        # 1. Resolve POST-level context (region, group, direction, proximity)
        post_ctx = self._resolve_post_context(post)

        # 2. Process sections with inherited context
        for section in post.children:
            if isinstance(section, PDSection):
                self.process_section(section, inherited_ctx=post_ctx)

    # ----------------------------------------------------------- #

    def process_section(self, section: PDSection, inherited_ctx: Dict) -> None:
        """
        Section inherits post-level context, then merges its own context.
        """
        merged_ctx = self._merge_contexts(inherited_ctx, section.contexts)

        for event in section.children:
            if isinstance(event, PDEvent):
                self.process_event(event, merged_ctx)

    # ----------------------------------------------------------- #

    def process_event(self, event: PDEvent, inherited_ctx: Dict) -> None:
        """
        DOM logic for a single event:
          - merge contexts
          - region/group narrowing
          - resolve direction/proximity anchors
          - apply direction scoring
          - compute frontline distance
          - cluster-based final candidate selection
        """
        event_ctx = self._merge_contexts(inherited_ctx, event.contexts)

        # 1. Apply region/group narrowing immediately
        self._apply_event_context(event, event_ctx)

        # 2. Resolve direction/proximity anchors (LocaleEntry)
        anchor_map = self._resolve_event_anchors(event_ctx)

        # 3. Apply direction scoring (if anchors exist)
        apply_direction_context_to_event(event, anchor_map, self.frontline)

        # 4. Compute frontline distance for all candidates
        compute_frontline_distances(event, self.frontline)

        # 5. Final clustering-based candidate selection
        perform_candidate_clustering(event)

    # ===============================================================
    # CONTEXT HANDLING
    # ===============================================================

    def _resolve_post_context(self, post: PDPost) -> Dict:
        """
        Resolve top-level (post) context:
            region, group, direction, proximity
        """
        out = {
            "region": None,
            "group": None,
            "direction": None,
            "proximity": None,
        }

        for ctx in post.contexts:
            kind = ctx.kind.value

            if kind == "region":
                out["region"] = self.gaz.search_region(ctx.text)

            elif kind == "group":
                out["group"] = self.gaz.search_group(ctx.text)

            elif kind == "direction":
                out["direction"] = self.gaz.search_direction(ctx.text)

            elif kind == "proximity":
                out["proximity"] = self.gaz.search_direction(ctx.text)

        return out

    # ----------------------------------------------------------- #

    def _merge_contexts(self, higher: Dict, local: Iterable) -> Dict:
        """
        Merge inherited (post or section level) and local contexts.
        Local context overrides higher context.
        """
        out = dict(higher)

        for ctx in local:
            kind = ctx.kind.value

            if kind == "region":
                reg = self.gaz.search_region(ctx.text)
                if reg:
                    out["region"] = reg

            elif kind == "group":
                grp = self.gaz.search_group(ctx.text)
                if grp:
                    out["group"] = grp

            elif kind in ("direction", "proximity"):
                d = self.gaz.search_direction(ctx.text)
                if d:
                    out[kind] = d

        return out

    # ----------------------------------------------------------- #

    def _apply_event_context(self, event: PDEvent, ctx_map: Dict) -> None:
        """
        Apply region & group narrowing immediately to all PDLocation nodes.
        """
        region = ctx_map.get("region")
        group = ctx_map.get("group")

        for loc in event.children:
            if not isinstance(loc, PDLocation):
                continue

            if region:
                apply_region_context_to_event(loc, region)

            if group:
                apply_group_context_to_event(loc, group)

    # ----------------------------------------------------------- #

    def _resolve_event_anchors(self, ctx_map: Dict) -> Dict:
        """
        Resolve anchors for direction and proximity.

        Returns:
            {
                "direction": LocaleEntry | None,
                "proximity": LocaleEntry | None,
            }

        In the new Gazetteer:
            DirectionEntry.anchor is already a LocaleEntry.
        """
        anchor_map = {"direction": None, "proximity": None}

        for key in ("direction", "proximity"):
            d = ctx_map.get(key)
            if d is not None:
                anchor_map[key] = d.anchor  # already a LocaleEntry

        return anchor_map
