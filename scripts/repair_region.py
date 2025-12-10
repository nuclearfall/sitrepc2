import csv
import json
from shapely.geometry import shape, Point

# ------------------------------
# Load oblast polygons
# ------------------------------
with open("ua_admin4.geojson", "r", encoding="utf-8") as f:
    gj = json.load(f)

regions = []
for feat in gj["features"]:
    props = feat.get("properties", {})
    geom = shape(feat["geometry"])
    regions.append({
        "geom": geom,
        "osm_id": props.get("id"),
        "name_en": props.get("name:en")
    })

# ------------------------------
# Helper function: find region for point
# ------------------------------
def find_region(lon, lat):
    point = Point(lon, lat)

    containing = []

    # Simple, safe iteration over all oblast polygons
    for reg in regions:
        geom = reg["geom"]
        if geom.contains(point):
            containing.append(reg)

    # No region found
    if not containing:
        return None, None

    # Only one region found
    if len(containing) == 1:
        r = containing[0]
        return r["name_en"], r["osm_id"]

    # Multiple regions contain the point:
    # Choose the smallest area (this correctly assigns Kyiv to Kyiv city, not Oblast)
    smallest = min(containing, key=lambda r: r["geom"].area)
    return smallest["name_en"], smallest["osm_id"]


# ------------------------------
# Process settlements CSV
# ------------------------------
input_csv = "ua_settlements.csv"
output_csv = "ua_settlements_with_regions.csv"

with open(input_csv, "r", encoding="utf-8") as f_in, \
     open(output_csv, "w", encoding="utf-8", newline="") as f_out:

    reader = csv.DictReader(f_in)
    fieldnames = reader.fieldnames + ["region:name", "region:osm_id"]
    writer = csv.DictWriter(f_out, fieldnames=fieldnames)
    writer.writeheader()

    for row in reader:
        lat = float(row["lat"])
        lon = float(row["lon"])

        region_name, region_osm_id = find_region(lon, lat)

        row["region:name"] = region_name
        row["region:osm_id"] = region_osm_id

        writer.writerow(row)

print("Done. Output written to ua_settlements_with_regions.csv")
