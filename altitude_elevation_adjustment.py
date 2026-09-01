import os
import requests
from abc import ABC, abstractmethod
from math import ceil
from geopy.distance import geodesic
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ==========================================
# 1. THE INTERFACE & PROVIDERS
# ==========================================

class ElevationProvider(ABC):
    @abstractmethod
    def get_elevations(self, coordinates):
        pass


class OpenMeteoProvider(ElevationProvider):
    def get_elevations(self, coordinates):
        elevations = []
        chunk_size = 500

        for i in range(0, len(coordinates), chunk_size):
            chunk = coordinates[i:i + chunk_size]
            lats = [c[0] for c in chunk]
            lons = [c[1] for c in chunk]

            url = "https://api.open-meteo.com/v1/elevation"

            try:
                r = requests.get(url, params={
                    "latitude": ",".join(map(str, lats)),
                    "longitude": ",".join(map(str, lons))
                }, timeout=10)

                r.raise_for_status()
                elevations.extend(r.json().get('elevation', []))

            except Exception as e:
                print(f"[OpenMeteo] Error: {e}")
                elevations.extend([0.0] * len(chunk))

        return elevations


class GoogleMapsProvider(ElevationProvider):
    def __init__(self, api_key=None):
        """
        Args:
            api_key (str, optional): The raw API key. If not provided,
                                     it automatically falls back to the .env file.
        """
        # 1st Priority: Passed explicitly in the code/API request
        # 2nd Priority: Loaded from the .env file / OS environment
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')

        if not self.api_key:
            print(
                "[Google] Warning: No API key provided and GOOGLE_API_KEY not found in environment.")

    def get_elevations(self, coordinates):
        if not self.api_key:
            print("[Google] Error: Cannot fetch elevations. No valid API Key loaded.")
            return [0.0] * len(coordinates)

        elevations = []
        chunk_size = 200

        for i in range(0, len(coordinates), chunk_size):
            chunk = coordinates[i:i + chunk_size]
            locations = "|".join(
                [f"{lat:.6f},{lon:.6f}" for lat, lon in chunk])

            url = "https://maps.googleapis.com/maps/api/elevation/json"

            try:
                r = requests.get(
                    url,
                    params={
                        "locations": locations,
                        "key": self.api_key,
                    },
                    timeout=(3, 15),
                )

                print(
                    f"[Google] Status code: {r.status_code}, points: {len(chunk)}")

                result = r.json()
                status = result.get("status")

                if status == "OK":
                    elevations.extend([item["elevation"]
                                      for item in result["results"]])
                else:
                    print(
                        f"[Google] API Error: {status} - {result.get('error_message', '')}")
                    elevations.extend([0.0] * len(chunk))

            except Exception as e:
                print(f"[Google] Request Failed: {e}")
                elevations.extend([0.0] * len(chunk))

        return elevations


# ==========================================
# 2. MAIN LOGIC
# ==========================================

def adjust_trajectory_to_terrain(trajectory, reference_point, provider: ElevationProvider,
                                 interpolation_step=10, vertical_step=3):
    """
    Adjusts a trajectory to follow ground elevation.
    Guarantees that ALL original waypoints are kept.
    Adds intermediate waypoints only if terrain height changes > vertical_step.
    """

    # --- Phase 1: Interpolate & Tag Points ---
    interpolated_path = []

    p_start = trajectory[0].copy()
    p_start['is_original'] = True
    interpolated_path.append(p_start)

    for i in range(len(trajectory) - 1):
        p1 = trajectory[i]['position']['coordinates']
        p2 = trajectory[i + 1]['position']['coordinates']

        # Calculate horizontal distance
        dist = geodesic((p1[1], p1[0]), (p2[1], p2[0])).meters

        # Handle vertical-only movements explicitly
        if dist == 0.0:
            pass
        elif dist > interpolation_step:
            num_segments = ceil(dist / interpolation_step)
            for j in range(1, num_segments):
                fraction = j / num_segments

                new_lat = p1[1] + (p2[1] - p1[1]) * fraction
                new_lon = p1[0] + (p2[0] - p1[0]) * fraction
                new_alt = p1[2] + (p2[2] - p1[2]) * fraction

                interpolated_path.append({
                    'actions': [],
                    'position': {
                        'type': 'Point',
                        'coordinates': [new_lon, new_lat, new_alt]
                    },
                    'sequenceIndex': trajectory[i]['sequenceIndex'],
                    'is_original': False
                })

        # Add the next original waypoint
        p_next = p2.copy()
        interpolated_path.append({
            'actions': [],
            'position': {
                'type': 'Point',
                'coordinates': [p_next[0], p_next[1], p_next[2]]
            },
            'sequenceIndex': trajectory[i + 1]['sequenceIndex'],
            'is_original': True
        })

    # --- Phase 2: Fetch Elevations ---
    coords_to_query = [(reference_point['coordinates'][1], reference_point['coordinates'][0])]
    coords_to_query += [(p['position']['coordinates'][1], p['position']['coordinates'][0]) for p in interpolated_path]

    all_elevations = provider.get_elevations(coords_to_query)

    if not all_elevations:
        return trajectory

    ref_ground_elev = all_elevations[0]
    path_ground_elevs = all_elevations[1:]

    # --- Phase 3: Adjust Altitudes & Smart Filter ---
    final_path = []

    adjusted_candidates = []
    for i, p in enumerate(interpolated_path):
        ground_elev = path_ground_elevs[i]
        delta = ground_elev - ref_ground_elev
        p['position']['coordinates'][2] = round(p['position']['coordinates'][2] + delta, 2)
        p['ground_elev'] = ground_elev
        adjusted_candidates.append(p)

    final_path.append(adjusted_candidates[0])
    last_kept_alt = adjusted_candidates[0]['position']['coordinates'][2]

    for i in range(1, len(adjusted_candidates)):
        current_p = adjusted_candidates[i]

        is_mandatory = current_p.get('is_original', False)
        diff = abs(current_p['position']['coordinates'][2] - last_kept_alt)

        if is_mandatory:
            final_path.append(current_p)
            last_kept_alt = current_p['position']['coordinates'][2]
        elif diff >= vertical_step:
            final_path.append(current_p)
            last_kept_alt = current_p['position']['coordinates'][2]
        else:
            pass

    for p in final_path:
        p.pop('is_original', None)

    return final_path


if __name__ == "__main__":
    # Define Home (Takeoff location)
    home = {'lat': 40.57353, 'lon': 22.9970623, 'alt': 0}

    # Added a vertical ascent example to the start of the mission
    mission = [
        {'sequenceIndex': 0, 'position': {'coordinates': [22.9970623, 40.57353, 0]}},   # Ground
        {'sequenceIndex': 1, 'position': {'coordinates': [22.9970623, 40.57353, 60]}},  # Vertical Climb
        {'sequenceIndex': 2, 'position': {'coordinates': [22.9977901, 40.580472, 60]}}  # Horizontal Flight
    ]

    # Initialize the provider (automatically reads from .env)
    my_provider = GoogleMapsProvider()

    result = adjust_trajectory_to_terrain(
        trajectory=mission,
        reference_point=home,
        provider=my_provider,
        interpolation_step=10,
        vertical_step=3
    )

    print(f"Original Waypoints: {len(mission)}")
    print(f"Terrain Following Waypoints: {len(result)}")

    for wp in result:
        print(
            f"Lat: {wp['position']['coordinates'][1]:.5f} | Alt: {wp['position']['coordinates'][2]}m (Ground: {wp.get('ground_elev', 0)}m)")
