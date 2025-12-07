#encoding.py

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


def decode_coord_u64(key: int) -> tuple[float, float]:
    """Decode a 64-bit coordinate key back into (lat, lon)."""
    lat_u32 = key >> 32
    lon_u32 = key & 0xFFFFFFFF

    lat = lat_u32 / 1_000_000 - 90.0
    lon = lon_u32 / 1_000_000 - 180.0

    return round(lat, 6), round(lon, 6)


