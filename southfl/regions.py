"""Coarse discovery rectangles, NOT ecosystem boundaries or hydrological connectivity.

All bounds in (west, south, east, north) WGS84. Overlap is intentional: a
station can have multiple candidate regions, to be refined by GIS polygons.
"""
REGIONS = {
    "north_biscayne": (-80.32, 25.78, -80.08, 26.00),
    "central_south_biscayne": (-80.52, 25.33, -80.08, 25.80),
    "florida_bay": (-81.35, 24.75, -80.30, 25.35),
    "upper_keys": (-80.85, 24.80, -80.15, 25.30),
    "middle_keys": (-81.35, 24.55, -80.65, 24.96),
    "lower_keys": (-82.15, 24.37, -81.00, 24.82),
    "dry_tortugas": (-83.12, 24.38, -82.55, 24.82),
    # Inland and west-coast screening areas. Overlaps are intentional and
    # not statements about water transport or ecosystem boundaries.
    "everglades_interior": (-81.22, 25.25, -80.35, 26.54),
    "big_cypress": (-81.93, 25.62, -80.91, 26.50),
    "southwest_everglades_coast": (-82.45, 25.05, -81.05, 26.18),
    "lake_okeechobee": (-81.16, 26.67, -80.45, 27.34),
    "everglades_agricultural_area": (-81.20, 26.23, -80.33, 26.87),
    "caloosahatchee": (-82.68, 26.31, -81.47, 26.91),
    "st_lucie_connection": (-80.83, 26.91, -80.04, 27.43),
}
# Envelope is used for broad API discovery only; do not interpret it as
# ecological inclusion or evidence of water movement.
DOMAIN = (-83.15, 24.30, -80.00, 27.48)


def inside(lat, lon, bbox):
    if lat is None or lon is None:
        return False
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    w, s, e, n = bbox
    return w <= lon <= e and s <= lat <= n


def regions_for(lat, lon):
    return [name for name, bounds in REGIONS.items() if inside(lat, lon, bounds)]


def parse_bbox(value):
    parts = [float(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox requires west,south,east,north")
    w, s, e, n = parts
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("invalid bbox coordinates")
    return tuple(parts)
