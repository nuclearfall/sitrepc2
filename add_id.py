import csv
import json
from pathlib import Path

def encode_coord_u64(lat: float, lon: float) -> int:
    """Encode (lat, lon) into a single 64-bit integer key with 6-decimal precision."""
    # Normalize
    lat = round(lat, 6)
    lon = round(lon, 6)

    # Convert to unsigned 32-bit spaces
    lat_u32 = int((lat + 90.0) * 1_000_000)
    lon_u32 = int((lon + 180.0) * 1_000_000)

    # Pack
    return (lat_u32 << 32) | lon_u32
    
# Paths
base_dir = Path("src/sitrepc2/reference")
orig_path = base_dir / "locale_lookup.csv"
bak_path = base_dir / "locale_lookup.csv.bak"

# 1. Backup original
if not orig_path.exists():
    raise FileNotFoundError(f"Original file not found: {orig_path}")

orig_path.rename(bak_path)
print(f"Backed up original file to: {bak_path}")

# 2. Create new output file
new_path = base_dir / "locale_lookup.csv"

with bak_path.open("r", encoding="utf8", newline="") as f_in:
    reader = csv.DictReader(f_in)

    new_fields = [
        "name", "aliases", "place", "wikidata",
        "region", "ru_group", "usage",
        "lon", "lat", "cid"
    ]

    with new_path.open("w", encoding="utf8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=new_fields)
        writer.writeheader()

        # Ukraine bounding box
        MIN_LON, MAX_LON = 22.0, 41.0
        MIN_LAT, MAX_LAT = 43.0, 53.0

        def in_bbox(lon, lat):
            return MIN_LON <= lon <= MAX_LON and MIN_LAT <= lat <= MAX_LAT

        for row in reader:

            # Safe retrieval of coordinates field
            raw = (row.get("coordinates") or "").strip()

            if not raw:
                print(f"WARNING: Missing coordinates for '{row.get('name','')}', skipping.")
                continue

            # Parse coordinate array
            try:
                coords = json.loads(raw)
                if not (isinstance(coords, list) and len(coords) == 2):
                    raise ValueError("Coordinate array must be length-2.")
                a, b = float(coords[0]), float(coords[1])
            except Exception as e:
                print(f"WARNING: Invalid coordinate format for '{row.get('name','')}': {raw}")
                continue

            # Try interpretation 1: [lon, lat]
            lon, lat = a, b
            if in_bbox(lon, lat):
                pass
            else:
                # Try swapped: [lat, lon]
                lon_swapped, lat_swapped = b, a
                if in_bbox(lon_swapped, lat_swapped):
                    lon, lat = lon_swapped, lat_swapped
                else:
                    print(f"WARNING (bbox): Neither ordering fits Ukraine for '{row.get('name','')}', using original ordering.")

            # Encode canonical 64-bit coordinate key
            try:
                cid = encode_coord_u64(lat, lon)
            except Exception as e:
                print(f"ERROR encoding CID for '{row.get('name','')}': {e}")
                continue

            new_row = {
                "name": row.get("name", ""),
                "aliases": row.get("aliases", ""),
                "place": row.get("place", ""),
                "wikidata": row.get("wikidata", ""),
                "region": row.get("region", ""),
                "ru_group": row.get("ru_group", ""),
                "usage": row.get("usage", ""),
                "lon": lon,
                "lat": lat,
                "cid": cid
            }

            writer.writerow(new_row)

print(f"SUCCESS: Created updated locale_lookup.csv → {new_path}")
