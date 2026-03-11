import os
import requests
from abc import ABC, abstractmethod
from math import ceil
from geopy.distance import geodesic


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

            # Using POST is better for large data, but GET is standard for this free API.
            # reducing chunk_size ensures the URL stays short.
            try:
                r = requests.get(url, params={
                    "latitude": ",".join(map(str, lats)),
                    "longitude": ",".join(map(str, lons))
                }, timeout=10)

                r.raise_for_status()
                elevations.extend(r.json().get('elevation', []))

            except Exception as e:
                print(f"[OpenMeteo] Error: {e}")
                # Fill with 0.0s to maintain index alignment
                elevations.extend([0.0] * len(chunk))

        return elevations

class GoogleMapsProvider(ElevationProvider):
    def __init__(self, api_key_or_file):
        """
        Args:
            api_key_or_file (str): Can be a raw API Key string OR a path to a file (e.g. 'google_api_key.txt')
        """
        if os.path.isfile(api_key_or_file):
            try:
                with open(api_key_or_file, "r") as f:
                    self.api_key = f.read().strip()
            except Exception as e:
                print(f"[Google] Error reading key file: {e}")
                self.api_key = None
        else:
            self.api_key = api_key_or_file.strip()

    def get_elevations(self, coordinates):
        if not self.api_key:
            print("[Google] Error: No valid API Key loaded.")
            return [0.0] * len(coordinates)

        elevations = []
        chunk_size = 400

        for i in range(0, len(coordinates), chunk_size):
            chunk = coordinates[i:i + chunk_size]
            locations = "|".join([f"{lat},{lon}" for lat, lon in chunk])

            url = "https://maps.googleapis.com/maps/api/elevation/json"

            try:
                r = requests.get(url, params={"locations": locations, "key": self.api_key}, timeout=10)
                result = r.json()

                if result.get('status') == 'OK':
                    elevations.extend([item['elevation'] for item in result['results']])
                else:
                    print(f"[Google] API Error: {result.get('status')} - {result.get('error_message', '')}")
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
        p1 = trajectory[i]
        p2 = trajectory[i + 1]

        # Calculate horizontal distance
        dist = geodesic((p1['lat'], p1['lon']), (p2['lat'], p2['lon'])).meters

        # --- UPDATE: Handle vertical-only movements explicitly ---
        if dist == 0.0:
            # Same lat/lon (e.g., vertical climb/descent).
            # We skip horizontal interpolation completely.
            pass
        elif dist > interpolation_step:
            num_segments = ceil(dist / interpolation_step)
            for j in range(1, num_segments):
                fraction = j / num_segments

                new_lat = p1['lat'] + (p2['lat'] - p1['lat']) * fraction
                new_lon = p1['lon'] + (p2['lon'] - p1['lon']) * fraction
                new_alt = p1['alt'] + (p2['alt'] - p1['alt']) * fraction

                interpolated_path.append({
                    'lat': new_lat,
                    'lon': new_lon,
                    'alt': new_alt,
                    'is_original': False
                })

        # Add the next original waypoint
        p_next = p2.copy()
        p_next['is_original'] = True
        interpolated_path.append(p_next)

    # --- Phase 2: Fetch Elevations ---
    coords_to_query = [(reference_point['lat'], reference_point['lon'])]
    coords_to_query += [(p['lat'], p['lon']) for p in interpolated_path]

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
        p['alt'] = round(p['alt'] + delta, 2)
        p['ground_elev'] = ground_elev
        adjusted_candidates.append(p)

    final_path.append(adjusted_candidates[0])
    last_kept_alt = adjusted_candidates[0]['alt']

    for i in range(1, len(adjusted_candidates)):
        current_p = adjusted_candidates[i]

        is_mandatory = current_p.get('is_original', False)
        diff = abs(current_p['alt'] - last_kept_alt)

        if is_mandatory:
            final_path.append(current_p)
            last_kept_alt = current_p['alt']
        elif diff >= vertical_step:
            final_path.append(current_p)
            last_kept_alt = current_p['alt']
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
        {'lat': 40.57353, 'lon': 22.9970623, 'alt': 0},   # Ground
        {'lat': 40.57353, 'lon': 22.9970623, 'alt': 60},  # Vertical Climb
        {'lat': 40.580472, 'lon': 22.9977901, 'alt': 60}  # Horizontal Flight
    ]

    # my_provider = OpenMeteoProvider()
    my_provider = GoogleMapsProvider('google_api_key.txt')

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
        print(f"Lat: {wp['lat']:.5f} | Alt: {wp['alt']}m (Ground: {wp.get('ground_elev', 0)}m)")