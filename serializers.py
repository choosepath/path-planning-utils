import json

# Import your core logic modules
import time_estimation
import areas
import camera_related_utils
import altitude_elevation_adjustment as alt_adj
import weather_filtering


def process_fleet_filtering(json_input):
    """Transforms JSON, filters drone fleet by weather, returns JSON."""
    data = json.loads(json_input)

    # Extract coordinates (assuming they are passed in a "poi" object)
    poi = data.get('poi', {})
    lat = poi.get('lat')
    lon = poi.get('lon')
    vehicles = data.get('vehicles', [])

    if lat is None or lon is None:
        raise ValueError("Missing 'lat' or 'lon' in 'poi' object.")

    result = weather_filtering.filter_fleet_for_mission(lat, lon, vehicles)

    return json.dumps(result)


def process_time_estimation(json_input):
    """Transforms JSON to list, calculates flight time, returns JSON."""
    data = json.loads(json_input)

    # Extract and convert list of lists to list of tuples
    waypoints = [tuple(wp) for wp in data['waypoints']]
    max_speed = data['max_speed']
    accel = data.get('accel', 2.0)
    min_turn_speed = data.get('min_turn_speed', 1.0)

    # Call underlying function
    time_minutes = time_estimation.estimate_uav_flight_time(
        waypoints, max_speed, accel, min_turn_speed
    )

    # Format to dict and dump to JSON string
    output = {
        "estimated_time_minutes": round(time_minutes, 2),
        "estimated_time_seconds": round(time_minutes * 60, 2)
    }
    return json.dumps(output)


def process_polygon_area(json_input):
    """Transforms JSON to list, calculates area, returns JSON."""
    data = json.loads(json_input)
    waypoints = [tuple(wp) for wp in data['waypoints']]

    area = areas.calculate_polygon_area_wgs84(waypoints)

    output = {
        "area_sq_meters": round(area, 2),
    }
    return json.dumps(output)


def process_circle_area(json_input):
    """Transforms JSON, calculates circle area, returns JSON."""
    data = json.loads(json_input)
    radius = data['radius']

    area = areas.calculate_circle_area(radius)

    output = {
        "area_sq_meters": round(area, 2)
    }
    return json.dumps(output)


def process_flight_metrics(json_input):
    """Transforms JSON kwargs, calculates photogrammetry metrics, returns JSON."""
    data = json.loads(json_input)

    # The function accepts kwargs natively, so we pass the dictionary directly
    result = camera_related_utils.calculate_flight_metrics(**data)

    return json.dumps(result)


def process_altitude_adjustment(json_input):
    """Transforms JSON lists/dicts, adjusts terrain, returns JSON list."""
    data = json.loads(json_input)

    trajectory = data['trajectory']
    reference_point = data['reference_point']

    # Setup Provider
    provider_type = data.get('provider', 'open-meteo').lower()
    if provider_type == 'google':
        api_key = data.get('api_key', 'google_api_key.txt')
        provider = alt_adj.GoogleMapsProvider(api_key)
    else:
        provider = alt_adj.OpenMeteoProvider()

    interpolation_step = data.get('interpolation_step', 10)
    vertical_step = data.get('vertical_step', 3)

    # Call underlying function
    adjusted_trajectory = alt_adj.adjust_trajectory_to_terrain(
        trajectory, reference_point, provider, interpolation_step, vertical_step
    )

    output = {
        "original_count": len(trajectory),
        "adjusted_count": len(adjusted_trajectory),
        "trajectory": adjusted_trajectory
    }
    return json.dumps(output)