# src/sitrepc2/spatial/distance.py

from __future__ import annotations

import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the great-circle distance between two WGS84 points (lat, lon)
    in decimal degrees, using the Haversine formula.

    Returns distance in kilometers.
    """
    # Mean Earth radius (km) – IUGG 1980
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


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Convenience wrapper: haversine distance in meters.
    """
    return haversine_km(lat1, lon1, lat2, lon2) * 1000.0
