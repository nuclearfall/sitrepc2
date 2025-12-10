# ---------------------------------------------------------------------------
# candidate_narrowing.py
#
# Context-aware candidate generation before DOM scoring.
#
# This module performs EARLY pruning:
#   • region context → hard filter
#   • group context  → hard-but-fallback filter
#   • proximity → soft ordering + optional radius cutoff
#   • direction → NEVER a filter (scoring only)
#
# The goal: drastically reduce candidate explosion while keeping safety.
#
# ---------------------------------------------------------------------------

from __future__ import annotations
from typing import List, Optional, Sequence

from sitrepc2.events.typedefs import Location, Event, LocaleCandidate
from sitrepc2.nlp.typedefs import SitRepContext, CtxKind
from sitrepc2.gazetteer.index import GazetteerIndex
from sitrepc2.gazetteer.typedefs import LocaleEntry


# ---------------------------------------------------------------------------
# Helpers: small utilities
# ---------------------------------------------------------------------------

def _extract_first_context(
    contexts: Sequence[SitRepContext], kind: CtxKind
) -> Optional[SitRepContext]:
    """Return the *first* context of the given CtxKind, if any."""
    for ctx in contexts:
        if ctx.kind == kind:
            return ctx
    return None


def _unique_by_cid(locales: List[LocaleEntry]) -> List[LocaleEntry]:
    """Ensure no duplicates in candidate lists."""
    seen = set()
    out = []
    for loc in locales:
        if loc.cid not in seen:
            seen.add(loc.cid)
            out.append(loc)
    return out


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def narrow_candidates(
    event: Event,
    gaz: GazetteerIndex,
    *,
    proximity_radius_km: float = 50.0,
) -> None:
    """
    Populate and/or reduce candidate sets for each Location in the event
    using contextual information inherited from post/section/event level.

    This stage happens BEFORE:
        • preflight anchor resolution
        • scoring (direction, proximity scoring)
        • clustering

    After this is complete, event.locations[*].candidates contains
    *reduced* LocaleCandidate objects with significantly less noise.

    Parameters:
        event         – Event with .locations, already context-inherited.
        gaz           – GazetteerIndex for lookups.
        proximity_radius_km (default 50 km)
                      – If a proximity context exists and the anchor is
                        known, filter out candidates that exceed this range.
    """

    # --------------------------------------------
    # 1. Collect event-level inherited contexts
    # --------------------------------------------
    region_ctx: Optional[SitRepContext] = _extract_first_context(event.contexts, CtxKind.REGION)
    group_ctx: Optional[SitRepContext] = _extract_first_context(event.contexts, CtxKind.GROUP)
    proximity_ctx: Optional[SitRepContext] = _extract_first_context(event.contexts, CtxKind.PROXIMITY)
    # direction context is NOT used for early filtering

    region_name: Optional[str] = region_ctx.value if region_ctx else None
    group_name: Optional[str] = group_ctx.value if group_ctx else None

    # For proximity contexts: store anchor locale if resolved upstream
    proximity_anchor: Optional[LocaleEntry] = None
    if proximity_ctx and isinstance(proximity_ctx.value, LocaleEntry):
        proximity_anchor = proximity_ctx.value

    # --------------------------------------------
    # 2. Narrow each location
    # --------------------------------------------

    for loc in event.locations:
        raw_name = loc.text

        # ----------------------------------------------------
        # Step A. Base retrieval: region-aware or naive search
        # ----------------------------------------------------
        if region_name:
            region_filtered = gaz.search_locale_in_region(raw_name, region_name)
        else:
            region_filtered = gaz.search_locale(raw_name)

        region_filtered = _unique_by_cid(region_filtered)

        # Safety fallback: If region context filters out everything,
        # revert to naive search.
        if region_name and not region_filtered:
            region_filtered = gaz.search_locale(raw_name)

        # ----------------------------------------------------
        # Step B. Apply group context filter
        # ----------------------------------------------------
        if group_name:
            group_filtered = gaz.search_locale_in_ru_group(raw_name, group_name)
        else:
            group_filtered = region_filtered

        group_filtered = _unique_by_cid(group_filtered)

        # Intersection logic:
        if group_name and region_name:
            # Exact intersection
            cids = {l.cid for l in region_filtered}
            intersection = [l for l in group_filtered if l.cid in cids]
            if intersection:
                narrowed = intersection
            else:
                # Fallback to region — region is authoritative
                narrowed = region_filtered
        else:
            # No formal intersection needed
            if group_name:
                narrowed = group_filtered
            else:
                narrowed = region_filtered

        # --------------------------------------------
        # Step C. Apply proximity contextual narrowing
        # --------------------------------------------
        if proximity_anchor is not None:
            lat0, lon0 = proximity_anchor.lat, proximity_anchor.lon

            # compute distance for ordering & filtering
            scored = []
            for entry in narrowed:
                d = gaz._haversine_km(lat0, lon0, entry.lat, entry.lon)
                scored.append((d, entry))

            # sort by distance
            scored.sort(key=lambda t: t[0])

            # optional: hard radius limit
            pruned = [
                entry for (d, entry) in scored
                if d <= proximity_radius_km
            ]

            if pruned:
                narrowed = pruned
            else:
                # keep nearest few if nothing is within radius
                # do not discard everything
                narrowed = [entry for (_, entry) in scored[:5]]


            loc.candidates = []
            for entry in narrowed:
                cand = LocaleCandidate(locale=entry, confidence=0.0)

                # REGION CONTEXT CONFIDENCE
                if region_name:
                    if entry.region and entry.region.lower() == region_name.lower():
                        cand.confidence += 0.6
                    else:
                        cand.confidence -= 0.5

                # GROUP CONTEXT CONFIDENCE
                if group_name:
                    if entry.ru_group == group_name:
                        cand.confidence += 0.6
                    else:
                        cand.confidence -= 0.5

                # PROXIMITY CONFIDENCE (if proximity anchor exists)
                if proximity_anchor:
                    d = gaz._haversine_km(
                        proximity_anchor.lat, proximity_anchor.lon,
                        entry.lat, entry.lon
                    )
                    if d <= proximity_radius_km:
                        cand.confidence += 0.4
                    else:
                        cand.confidence -= 0.2
                    cand.scores["prox_km"] = d

                loc.candidates.append(cand)

            # If narrowed to 1, mark location "resolved" early.
            if len(loc.candidates) == 1:
                loc.selection = loc.candidates[0]
                loc.selection_confidence = loc.candidates[0].confidence

