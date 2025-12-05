import math
from collections.abc import Sequence

from sitrepc2.nlp.typedefs import EventLocationMention, LocationKind


def annotate_direction_for_mentions(
    frontline: Frontline,
    *,
    direction_city: LocaleEntry,
    mentions: Sequence[EventLocationMention],
    direction_label: str | None = None,
) -> Optional[DirectionAxis]:
    """
    Convenience wrapper:

    - Takes the list of EventLocationMentions for one event / section.
    - Filters to LOCALE mentions.
    - Flattens their locale_candidates into one list.
    - Calls annotate_direction_axis_for_candidates(...) on that list.

    Call this *before* choose_best_locale_cluster(), so that unary_score()
    can see dir_along_km / dir_cross_km on each candidate.
    """
    # Only LOCALE mentions with candidates matter here.
    all_candidates: list[LocaleCandidate] = []
    for m in mentions:
        if m.kind is not LocationKind.LOCALE:
            continue
        if not m.locale_candidates:
            continue
        all_candidates.extend(m.locale_candidates)

    if not all_candidates:
        return None

    return annotate_direction_axis_for_candidates(
        frontline,
        direction_city=direction_city,
        candidates=all_candidates,
        direction_label=direction_label,
    )

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes the great-circle distance between two points on Earth
    specified in decimal degrees using the Haversine formula.

    Parameters
    ----------
    lat1, lon1 : float
        Latitude and longitude of point 1.
    lat2, lon2 : float
        Latitude and longitude of point 2.

    Returns
    -------
    float
        Distance in kilometers.
    """
    # Mean Earth radius per IUGG 1980 (km)
    R = 6371.0088

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def haversine_m(lat1, lon1, lat2, lon2):
    return haversine_km(lat1, lon1, lat2, lon2) * 1000.0

