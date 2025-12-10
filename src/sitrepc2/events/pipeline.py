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
from sitrepc2.events.typedefs import Location


# ===============================================================
# DOM ENTRY POINT
# ===============================================================

class DOMProcessor:
    """
    Runs full DOM-level enrichment and resolution on a reviewed PD tree.

    This class does NOT mutate structure (no pruning).
    It ONLY enriches PD nodes with:
      - filtered candidate lists
      - anchor resolutions
      - distance metrics
      - direction axis projections
      - cluster results
      - final locale selection
    """

    def __init__(self, gaz: GazetteerIndex, frontline: Optional[Frontline] = None):
        self.gaz = gaz
        self.frontline = frontline

    # ----------------------------------------------------------- #
    # PUBLIC API
    # ----------------------------------------------------------- #

    def process_posts(self, posts: Iterable[PDPost]) -> None:
        """
        Entry point for batch processing.
        Mutates PD trees in place—does not return a new structure.
        """
        for post in posts:
            self.process_post(post)

    def process_post(self, post: PDPost) -> None:
        """
        Apply DOM processing to a single PDPost tree.
        """
        # 1. Resolve POST-level context (region, group, direction)
        resolved_ctx = self._resolve_post_context(post)

        # 2. Process sections
        for section in post.children:
            if isinstance(section, PDSection):
                self.process_section(section, inherited_ctx=resolved_ctx)

    # ----------------------------------------------------------- #

    def process_section(self, section: PDSection, inherited_ctx) -> None:
        """
        Apply DOM logic to a section.
        Section inherits any post-level context (hard constraints).
        """
        merged_ctx = self._merge_contexts(inherited_ctx, section.contexts)

        for event in section.children:
            if isinstance(event, PDEvent):
                self.process_event(event, merged_ctx)

    # ----------------------------------------------------------- #

    def process_event(self, event: PDEvent, inherited_ctx) -> None:
        """
        DOM logic for a single event:
          - merge contexts
          - resolve anchors for direction/proximity
          - filter candidates early
          - compute frontline distance
          - compute direction metrics
          - cluster resolution
        """
        event_ctx = self._merge_contexts(inherited_ctx, event.contexts)

        # Establish context-driven narrowing
        self._apply_event_context(event, event_ctx)

        # Anchor resolution for direction and proximity
        anchor_map = self._resolve_event_anchors(event_ctx)

        # Apply direction scoring (if anchors exist)
        apply_direction_context_to_event(event, anchor_map, self.frontline)

        # Frontline distance scoring (all candidates)
        compute_frontline_distances(event, self.frontline)

        # Cluster-based resolution → assigns one candidate per PDLocation
        perform_candidate_clustering(event)

    # ===============================================================
    # CONTEXT HANDLING
    # ===============================================================

    def _resolve_post_context(self, post: PDPost):
        """
        Returns a dictionary of:
            {
                'region': RegionEntry | None,
                'group': GroupEntry | None,
                'direction': DirectionEntry | None,
                'proximity': DirectionEntry | None
            }
        """
        out = {
            "region": None,
            "group": None,
            "direction": None,
            "proximity": None,
        }

        for ctx in post.contexts:
            if ctx.kind.value == "region":
                reg = self.gaz.search_region(ctx.text)
                if reg:
                    out["region"] = reg

            elif ctx.kind.value == "group":
                # TODO: search_group once added to GazetteerIndex
                pass

            elif ctx.kind.value == "direction":
                d = self.gaz.search_direction(ctx.text)  # <-- NEW METHOD
                if d:
                    out["direction"] = d

            elif ctx.kind.value == "proximity":
                d = self.gaz.search_direction(ctx.text)
                if d:
                    out["proximity"] = d

        return out

    # ----------------------------------------------------------- #

    def _merge_contexts(self, higher, local):
        """
        Merge inherited (higher-level) and local contexts.
        Local overrides higher.
        """
        out = dict(higher)

        for ctx in local:
            if ctx.kind.value == "region":
                reg = self.gaz.search_region(ctx.text)
                if reg:
                    out["region"] = reg

            elif ctx.kind.value == "group":
                pass

            elif ctx.kind.value in ("direction", "proximity"):
                d = self.gaz.search_direction(ctx.text)
                if d:
                    out[ctx.kind.value] = d

        return out

    # ----------------------------------------------------------- #

    def _apply_event_context(self, event: PDEvent, ctx_map: Dict):
        """
        Apply region & group narrowing immediately to all PDLocations.
        This removes candidates that contradict event-level context.
        """
        for loc in event.children:
            if not isinstance(loc, PDLocation):
                continue

            # Region narrowing
            if ctx_map["region"]:
                apply_region_context_to_event(loc, ctx_map["region"])

            # Group narrowing
            if ctx_map["group"]:
                apply_group_context_to_event(loc, ctx_map["group"])

    # ----------------------------------------------------------- #

    def _resolve_event_anchors(self, ctx_map):
        """
        Resolve anchors for direction/proximity.

        Returns:
            {
                "direction": LocaleEntry | None,
                "proximity": LocaleEntry | None,
            }
        """
        anchor_map = {"direction": None, "proximity": None}

        for key in ("direction", "proximity"):
            entry = ctx_map.get(key)
            if entry:
                # DirectionEntry.anchor is a CID
                anchor = self.gaz._locale_by_cid.get(entry.anchor)
                anchor_map[key] = anchor

        return anchor_map
