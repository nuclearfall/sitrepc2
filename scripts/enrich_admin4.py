#!/usr/bin/env python
"""
Build oblast regions and enrich ua_settlements.csv using the Geofabrik shapefile.

Inputs:
    data/spatial/ukraine_shp/gis_osm_admin_a_free_1.shp
    data/spatial/ua_settlements.csv

Outputs:
    src/sitrepc2/reference/regions.csv
    src/sitrepc2/reference/settlements.csv
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# PROJECT_ROOT = Path(__file__).resolve()  # adjust if you put this elsewhere

DATA_DIR = Path("data") / "spatial"
SHP_DIR = DATA_DIR / "ukraine_shp"
ADMIN_SHP = SHP_DIR / "gis_osm_admin_a_free_1.shp"

SETTLEMENTS_CSV = DATA_DIR / "ua_settlements.csv"

REF_DIR =  Path("src") / "sitrepc2" / "reference"
REGIONS_CSV = REF_DIR / "regions.csv"
ENRICHED_SETTLEMENTS_CSV = REF_DIR / "settlements.csv"


# ---------------------------------------------------------------------------
# Step A: Build regions table from shapefile
# ---------------------------------------------------------------------------

def build_regions() -> gpd.GeoDataFrame:
    """
    Load admin polygons, filter to oblast-level (admin_level == 4),
    and write a regions.csv lookup.

    Returns:
        GeoDataFrame of oblast polygons (for later spatial join).
    """
    if not ADMIN_SHP.exists():
        raise FileNotFoundError(f"Admin shapefile not found: {ADMIN_SHP}")

    REF_DIR.mkdir(parents=True, exist_ok=True)

    gdf = gpd.read_file(ADMIN_SHP)

    # admin_level may be str or int; normalise to str for comparison
    admin_level_col = "admin_level"
    if admin_level_col not in gdf.columns:
        raise KeyError(
            f"Expected 'admin_level' column in {ADMIN_SHP}, found: {list(gdf.columns)}"
        )

    oblasts = gdf[gdf[admin_level_col].astype(str) == "4"].copy()

    if oblasts.empty:
        raise RuntimeError("No admin_level=4 polygons found in admin shapefile.")

    # Try to discover useful columns; fall back gracefully if missing
    name_col = "name" if "name" in oblasts.columns else None
    osm_id_col = "osm_id" if "osm_id" in oblasts.columns else None

    if osm_id_col is None:
        raise KeyError(
            f"Expected an 'osm_id' column in admin shapefile; found: {list(oblasts.columns)}"
        )

    # Optional metadata columns – will be mostly None/empty if not present
    wikidata_col = "wikidata" if "wikidata" in oblasts.columns else None
    iso_col = "ISO3166-2" if "ISO3166-2" in oblasts.columns else None
    name_uk_col = "name:uk" if "name:uk" in oblasts.columns else None
    name_en_col = "name:en" if "name:en" in oblasts.columns else None

    records = []
    for _, row in oblasts.iterrows():
        records.append(
            {
                "region:osm_id": row[osm_id_col],
                "region:name": row[name_col] if name_col else None,
                # These may be empty depending on shapefile contents; we keep the columns
                "region:name:uk": row[name_uk_col] if name_uk_col else None,
                "region:name:en": row[name_en_col] if name_en_col else None,
                "region:wikidata": row[wikidata_col] if wikidata_col else None,
                "region:iso": row[iso_col] if iso_col else None,
                "admin_level": row[admin_level_col],
            }
        )

    regions_df = pd.DataFrame.from_records(records)

    # Basic sanity-sort by name for human readability
    if "region:name" in regions_df.columns:
        regions_df = regions_df.sort_values("region:name")

    regions_df.to_csv(REGIONS_CSV, index=False)
    print(f"Saved regions lookup → {REGIONS_CSV}")

    return oblasts


# ---------------------------------------------------------------------------
# Step B/C: Enrich settlements via spatial join
# ---------------------------------------------------------------------------

def enrich_settlements(oblasts: gpd.GeoDataFrame) -> None:
    """
    Spatially join settlements to oblast polygons.

    Writes an enriched settlements.csv with a region foreign key.
    """
    if not SETTLEMENTS_CSV.exists():
        raise FileNotFoundError(f"Settlements CSV not found: {SETTLEMENTS_CSV}")

    df = pd.read_csv(SETTLEMENTS_CSV)

    # Expected original headers (from your example):
    # osm_type,osm_id,place,name,name:uk,wikidata,lat,lon
    missing = [col for col in ("osm_id", "lat", "lon") if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns in settlements CSV: {missing}")

    # Build GeoDataFrame of points
    points_gdf = gpd.GeoDataFrame(
        df.copy(),
        geometry=[Point(xy) for xy in zip(df["lon"], df["lat"])],
        crs="EPSG:4326",
    )

    # Ensure oblast geometries are also in EPSG:4326
    if oblasts.crs is None:
        oblasts = oblasts.set_crs("EPSG:4326", allow_override=True)
    else:
        oblasts = oblasts.to_crs("EPSG:4326")

    # Minimal set of columns we need from oblasts
    # We know we have at least osm_id; name is optional
    cols_for_join = ["osm_id", "geometry"]
    if "name" in oblasts.columns:
        cols_for_join.append("name")

    oblasts_for_join = oblasts[cols_for_join].copy()

    # Spatial join: which oblast contains each settlement
    joined = gpd.sjoin(
        points_gdf,
        oblasts_for_join,
        how="left",
        predicate="within",  # settlements should be inside one oblast
    )

    # Rename joined columns
    rename_map = {}
    if "osm_id_right" in joined.columns:
        rename_map["osm_id_right"] = "region:osm_id"
    if "name_right" in joined.columns:
        rename_map["name_right"] = "region:name"

    joined = joined.rename(columns=rename_map)

    # Drop spatial join helper columns we don't want in final CSV
    for col in ("index_right", "geometry"):
        if col in joined.columns:
            joined = joined.drop(columns=[col])

    # Mark whether a settlement has been matched to some oblast
    joined["region:confirmed"] = joined["region:osm_id"].notna()

    # We no longer need osm_type in the final relational table
    if "osm_type" in joined.columns:
        joined = joined.drop(columns=["osm_type"])

    # Final column order (keep only those that actually exist)
    desired_cols = [
        "osm_id",
        "place",
        "name",
        "name:uk",
        "lat",
        "lon",
        "wikidata",
        "region:osm_id",
        "region:name",
        "region:confirmed",
    ]
    final_cols = [c for c in desired_cols if c in joined.columns]

    REF_DIR.mkdir(parents=True, exist_ok=True)
    joined[final_cols].to_csv(ENRICHED_SETTLEMENTS_CSV, index=False)

    total = len(joined)
    matched = int(joined["region:confirmed"].sum())
    unmatched = total - matched

    print(f"Saved enriched settlements → {ENRICHED_SETTLEMENTS_CSV}")
    print(f"Total settlements: {total}")
    print(f"Matched to oblast: {matched}")
    print(f"Unmatched (no containing oblast): {unmatched}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    oblasts = build_regions()
    enrich_settlements(oblasts)


if __name__ == "__main__":
    main()
