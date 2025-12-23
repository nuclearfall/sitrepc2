from __future__ import annotations

from enum import Enum
from typing import Dict, List

from sitrepc2.spatial.distance import haversine_km
from nodes import LocationNode, LocationCandidateNode, Context


# ============================================================
# EXCLUSION REASONS (AUDITABLE)
# ============================================================

class ExclusionReason(Enum):
    USER_DESELECTED = "user_deselected"
    REGION_MISMATCH = "region_mismatch"
    GROUP_MISMATCH = "group_mismatch"
    DIRECTION_DISTANCE = "direction_distance"


# ============================================================
# GAZETTEER-BACKED COMPATIBILITY CHECKS
# ============================================================

def is_region_compatible(
    gaz_conn,
    location_id: int,
    region_id: int,
) -> bool | None:
    """
    REGION compatibility via location_regions.

    Returns:
        True  -> compatible
        False -> incompatible
        None  -> indeterminate
    """
    row = gaz_conn.execute(
        """
        SELECT 1
        FROM location_regions
        WHERE location_id = ? AND region_id = ?
        """,
        (location_id, region_id),
    ).fetchone()

    if row:
        return True

    any_region = gaz_conn.execute(
        """
        SELECT 1
        FROM location_regions
        WHERE location_id = ?
        LIMIT 1
        """,
        (location_id,),
    ).fetchone()

    if any_region:
        return False

    return None


def is_group_compatible(
    gaz_conn,
    location_id: int,
    group_id: int,
) -> bool | None:
    """
    GROUP compatibility via location_groups.

    Returns:
        True  -> compatible
        False -> incompatible
        None  -> indeterminate
    """
    row = gaz_conn.execute(
        """
        SELECT 1
        FROM location_groups
        WHERE location_id = ? AND group_id = ?
        """,
        (location_id, group_id),
    ).fetchone()

    if row:
        return True

    any_group = gaz_conn.execute(
        """
        SELECT 1
        FROM location_groups
        WHERE location_id = ?
        LIMIT 1
        """,
        (location_id,),
    ).fetchone()

    if any_group:
        return False

    return None


def is_direction_compatible(
    gaz_conn,
    candidate: LocationCandidateNode,
    direction_id: int,
    max_distance_km: float,
) -> bool | None:
    """
    DIRECTION compatibility via directions + fixed distance threshold.

    Returns:
        True  -> compatible
        False -> incompatible
        None  -> indeterminate
    """
    row = gaz_conn.execute(
        """
        SELECT anchor_id, anchor_type
        FROM directions
        WHERE direction_id = ?
        """,
        (direction_id,),
    ).fetchone()

    if row is None:
        return None

    anchor_id, anchor_type = row

    if candidate.lat is None or candidate.lon is None:
        return None

    if anchor_type == "LOCATION":
        anchor = gaz_conn.execute(
            """
            SELECT lat, lon
            FROM locations
            WHERE location_id = ?
            """,
            (anchor_id,),
        ).fetchone()
        if anchor is None:
            return None
        lat0, lon0 = anchor

    elif anchor_type == "REGION":
        # Assumes region anchor has a representative point
        anchor = gaz_conn.execute(
            """
            SELECT lat, lon
            FROM locations
            WHERE location_id = ?
            """,
            (anchor_id,),
        ).fetchone()
        if anchor is None:
            return None
        lat0, lon0 = anchor

    else:
        return None

    distance = haversine_km(candidate.lat, candidate.lon, lat0, lon0)
    return distance <= max_distance_km


# ============================================================
# MAIN FILTERING ENTRY POINT
# ============================================================

def filter_location_candidates(
    *,
    gaz_conn,
    location_node: LocationNode,
    applied_contexts: List[Context],
    max_direction_distance_km: float = 50.0,
) -> Dict[LocationCandidateNode, List[ExclusionReason]]:
    """
    Apply Phase 5c candidate filtering rules.

    Returns:
        Mapping of candidate -> list of exclusion reasons.
        Candidates with an empty list are eligible.
    """

    results: Dict[LocationCandidateNode, List[ExclusionReason]] = {}

    for candidate in location_node.children:
        if not isinstance(candidate, LocationCandidateNode):
            continue

        reasons: List[ExclusionReason] = []

        # Absolute exclusion: user deselection
        if not candidate.selected:
            results[candidate] = [ExclusionReason.USER_DESELECTED]
            continue

        for ctx in applied_contexts:
            if not ctx.selected:
                continue

            if (
                ctx.ctx_kind == "REGION"
                and candidate.gazetteer_location_id is not None
            ):
                ok = is_region_compatible(
                    gaz_conn,
                    candidate.gazetteer_location_id,
                    int(ctx.value),
                )
                if ok is False:
                    reasons.append(ExclusionReason.REGION_MISMATCH)

            elif (
                ctx.ctx_kind == "GROUP"
                and candidate.gazetteer_location_id is not None
            ):
                ok = is_group_compatible(
                    gaz_conn,
                    candidate.gazetteer_location_id,
                    int(ctx.value),
                )
                if ok is False:
                    reasons.append(ExclusionReason.GROUP_MISMATCH)

            elif ctx.ctx_kind == "DIRECTION":
                ok = is_direction_compatible(
                    gaz_conn,
                    candidate,
                    int(ctx.value),
                    max_direction_distance_km,
                )
                if ok is False:
                    reasons.append(ExclusionReason.DIRECTION_DISTANCE)

        results[candidate] = reasons

    return results
