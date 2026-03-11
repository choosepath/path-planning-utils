import math
from pyproj import Geod

def calculate_polygon_area_ned(points):
    """
    Calculates the area of a polygon in a Cartesian (NED) system.

    Args:
        points: List of tuples [(n, e), ...] or [(n, e, d), ...] in meters.
                (North/X, East/Y).

    Returns:
        float: Area in square meters.
    """
    # Implementation of the Shoelace Formula (Surveyor's Formula)
    area = 0.0
    n = len(points)

    if n < 3:
        return 0.0

    for i in range(n):
        j = (i + 1) % n  # Wrap around to the first point
        # x = North, y = East
        # Area = 0.5 * |sum(x_i * y_i+1 - x_i+1 * y_i)|
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]

    return abs(area) / 2.0


def calculate_polygon_area_wgs84(waypoints):
    """
        Calculates the exact geodesic area of a WGS84 polygon
        on the Earth ellipsoid using Karney's algorithm.
        """
    if len(waypoints) < 3:
        return 0.0

    # Initialize WGS84 ellipsoid
    geod = Geod(ellps="WGS84")

    lats = [p[0] for p in waypoints]
    lons = [p[1] for p in waypoints]

    # polygon_area_perimeter returns (area, perimeter)
    # The area can be positive or negative depending on winding (CW/CCW)
    area, perimeter = geod.polygon_area_perimeter(lons, lats)

    return abs(area)


def calculate_circle_area(radius_meters):
    """
    Calculates the area of a circle.

    Args:
        radius_meters: Radius in meters.

    Returns:
        float: Area in square meters.
    """
    return math.pi * (radius_meters ** 2)


# --- Helper Function (Optional) ---
def get_radius_from_wgs84(center, edge_point):
    """
    Helper: Calculates radius in meters between a center Lat/Lon
    and an edge Lat/Lon to feed into the circle area function.
    """
    R_EARTH = 6378137.0
    d_lat = math.radians(edge_point[0] - center[0])
    d_lon = math.radians(edge_point[1] - center[1])
    a = (math.sin(d_lat / 2) * math.sin(d_lat / 2) +
         math.cos(math.radians(center[0])) * math.cos(math.radians(edge_point[0])) *
         math.sin(d_lon / 2) * math.sin(d_lon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R_EARTH * c

if __name__ == '__main__':

    # 1. Define a polygon (Square ~100x100m) in WGS84
    polygon_geo = [
        (37.9838, 23.7275),
        (37.9847, 23.7275),
        (37.9847, 23.7286),
        (37.9838, 23.7286)
    ]

    # 2. Define a polygon in NED (Relative meters)
    polygon_ned = [
        (0, 0),
        (100, 0),
        (100, 100),
        (0, 100)
    ]

    # Calculate Areas
    area_geo = calculate_polygon_area_wgs84(polygon_geo)
    area_ned = calculate_polygon_area_ned(polygon_ned)
    area_circle = calculate_circle_area(radius_meters=50)

    print(f"WGS84 Polygon Area: {area_geo:.2f} m²")
    print(f"NED Polygon Area:   {area_ned:.2f} m²")
    print(f"Circle Area (r=50): {area_circle:.2f} m²")