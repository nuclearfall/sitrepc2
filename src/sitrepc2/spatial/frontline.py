from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import nearest_points, unary_union
from pyproj import Transformer

Coord = Tuple[float, float]  # (lon, lat)


def _collect_lines(gj: dict) -> List[List[Coord]]:
    lines: List[List[Coord]] = []
    for ft in gj.get("features", []):
        geom = ft.get("geometry", {})
        t = geom.get("type")
        if t == "LineString":
            lines.append(geom["coordinates"])
        elif t == "MultiLineString":
            lines.extend(geom["coordinates"])
        elif t == "Polygon":
            if geom.get("coordinates"):
                lines.append(geom["coordinates"][0])  # outer ring
        elif t == "MultiPolygon":
            for poly in geom.get("coordinates", []):
                if poly:
                    lines.append(poly[0])
    return lines


@dataclass(frozen=True)
class DirectionAxis:
    """
    City → frontline axis for “<City> direction” scoring.

    All lat/lon in WGS84 degrees.

    - city_*   : the direction city (e.g., Slavyansk).
    - anchor_* : the single chosen point on the LoC representing that direction.
    """
    city_lat: float
    city_lon: float
    anchor_lat: float
    anchor_lon: float


class Frontline:
    """
    Frontline distance helper.

    - Stores the LoC as a single Shapely geometry in a *metric* projection.
    - shortest_distance_km(lat, lon) returns shortest distance in kilometers.
    - Also supports directional axes (city → LoC anchor) for “direction of X”.
    """

    def __init__(self, polylines_wgs84: List[List[Coord]]):
        # 1) Transformers between lon/lat (EPSG:4326) and a metric CRS.
        self._to_metric = Transformer.from_crs(
            "EPSG:4326",
            "EPSG:3857",
            always_xy=True,  # lon, lat
        )
        self._to_wgs84 = Transformer.from_crs(
            "EPSG:3857",
            "EPSG:4326",
            always_xy=True,
        )

        # 2) Transform all polylines into metric coordinates and build LineStrings
        metric_lines = []
        for line in polylines_wgs84:
            if len(line) < 2:
                continue
            xs, ys = zip(*line)  # lon, lat
            mx, my = self._to_metric.transform(xs, ys)
            metric_lines.append(LineString(zip(mx, my)))

        if not metric_lines:
            self._geom = None
            return

        # 3) Merge into a single MultiLineString / LineString
        self._geom = unary_union(MultiLineString(metric_lines))

    # ------------------------------------------------------------------ #
    # Existing API
    # ------------------------------------------------------------------ #

    def shortest_distance_km(self, lat: float, lon: float) -> float:
        """
        Distance from (lat, lon) to LoC in kilometers.
        """
        if self._geom is None:
            return float("inf")

        mx, my = self._to_metric.transform(lon, lat)
        pt = Point(mx, my)
        d_m = self._geom.distance(pt)  # EPSG:3857 ~ meters
        return d_m / 1000.0

    # ------------------------------------------------------------------ #
    # New: city → frontline anchor and axis metrics
    # ------------------------------------------------------------------ #

    def anchor_for_city(
        self,
        city_lat: float,
        city_lon: float,
    ) -> Tuple[float, float] | None:
        """
        Return the *frontline* point (lat, lon) used as the anchor for a
        given direction city.

        This is the closest point on the LoC to (city_lat, city_lon), but,
        crucially, it is *stable* per city: you always use this anchor for
        that city when reasoning about “<City> direction”.
        """
        if self._geom is None:
            return None

        mx_c, my_c = self._to_metric.transform(city_lon, city_lat)
        city_pt = Point(mx_c, my_c)

        # Get nearest point on LoC in metric space.
        _, loc_pt_metric = nearest_points(city_pt, self._geom)
        lon_a, lat_a = self._to_wgs84.transform(loc_pt_metric.x, loc_pt_metric.y)
        return lat_a, lon_a

    def build_direction_axis(
        self,
        city_lat: float,
        city_lon: float,
    ) -> DirectionAxis | None:
        """
        Build a DirectionAxis for a given city.

        Returns None if LoC geometry is unavailable.
        """
        anchor = self.anchor_for_city(city_lat, city_lon)
        if anchor is None:
            return None
        anchor_lat, anchor_lon = anchor
        return DirectionAxis(
            city_lat=city_lat,
            city_lon=city_lon,
            anchor_lat=anchor_lat,
            anchor_lon=anchor_lon,
        )

    def axis_metrics_km(
        self,
        axis: DirectionAxis,
        lat: float,
        lon: float,
    ) -> Tuple[float, float]:
        """
        Compute (along_axis_km, cross_axis_km) for a point relative to a
        City→LoC DirectionAxis.

        - along_axis_km:
            signed distance along the ray from city to anchor.
            0 at the city, +D at the anchor, can be negative (behind city)
            or >D (beyond frontline).
        - cross_axis_km:
            absolute lateral distance from the infinite city↔anchor line.

        All distances are computed in the metric CRS and returned in km.
        """
        if self._geom is None:
            return 0.0, float("inf")

        # Transform city, anchor, and point to metric coordinates.
        mx_c, my_c = self._to_metric.transform(axis.city_lon, axis.city_lat)
        mx_a, my_a = self._to_metric.transform(axis.anchor_lon, axis.anchor_lat)
        mx_p, my_p = self._to_metric.transform(lon, lat)

        vx = mx_a - mx_c
        vy = my_a - my_c
        wx = mx_p - mx_c
        wy = my_p - my_c

        v_len = math.hypot(vx, vy)
        if v_len == 0.0:
            # Degenerate: city and anchor collapse. Treat as pure distance to city.
            along_m = 0.0
            cross_m = math.hypot(wx, wy)
            return along_m / 1000.0, cross_m / 1000.0

        # Scalar projection parameter t along the city→anchor vector.
        # t = 0 at city, t = 1 at anchor.
        t = (wx * vx + wy * vy) / (v_len * v_len)

        # Projection point on the infinite line.
        proj_x = mx_c + t * vx
        proj_y = my_c + t * vy

        along_m = t * v_len                  # signed: <0 behind, >v_len beyond
        cross_m = math.hypot(mx_p - proj_x, my_p - proj_y)

        return along_m / 1000.0, cross_m / 1000.0


def load_frontline(
    path: str | Path = "data/external/frontline/loc_polylines.geojson",
) -> Frontline | None:
    p = Path(path)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as f:
        gj = json.load(f)
    polylines = _collect_lines(gj)
    return Frontline(polylines)
