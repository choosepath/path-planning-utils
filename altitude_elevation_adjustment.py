from __future__ import annotations
import os
import requests
from abc import ABC, abstractmethod
from math import ceil
from geopy.distance import geodesic
from dotenv import load_dotenv

from dataclasses import dataclass
from math import atan2, ceil, cos, radians, sin, sqrt
from typing import Any

from geopy.distance import geodesic


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
        chunk_size = 250

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

def adjust_trajectory_to_terrain_old(trajectory, reference_point, provider: ElevationProvider,
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
                    'actions': trajectory[i]['actions'],
                    'role': trajectory[i]['role'],
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
            'actions': trajectory[i + 1]['actions'],
            'role': trajectory[i + 1]['role'],
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


EARTH_RADIUS_M = 6_371_000.0

# ---------------------------------------------------------------------------
# Internal defaults
#
# These are engineering constraints, not user-facing mission inputs.
# Ideally provider resolution / accuracy should come from the provider itself.
# ---------------------------------------------------------------------------

DEFAULT_HORIZONTAL_RESOLUTION_M = 10.0
DEFAULT_VERTICAL_ACCURACY_M = 1.0

# We sample somewhat more densely than nominal DEM resolution.
SAMPLING_RESOLUTION_FACTOR = 0.75

MIN_SAMPLING_SPACING_M = 2.0
MAX_SAMPLING_SPACING_M = 30.0

# How far below the ideal terrain-following trajectory we allow
# a simplified segment to go.
#
# This is intentionally strict.
MIN_BELOW_TARGET_TOLERANCE_M = 0.5

# How far above the ideal terrain-following trajectory we allow
# the simplified path to remain.
#
# Allowing more room above valleys can substantially reduce
# waypoint count.
MIN_ABOVE_TARGET_TOLERANCE_M = 2.0
MAX_ABOVE_TARGET_TOLERANCE_M = 8.0


@dataclass
class TerrainPoint:
    lon: float
    lat: float

    # Altitude before terrain adjustment.
    original_alt: float

    # Ground elevation returned by provider.
    ground_elev: float | None = None

    # Final desired terrain-following altitude.
    adjusted_alt: float | None = None

    # Location inside one original WP -> WP segment.
    # 0.0 = first original WP
    # 1.0 = second original WP
    fraction: float = 0.0

    is_original: bool = False

    # Index into original trajectory.
    source_waypoint_index: int | None = None


# ===========================================================================
# Geometry
# ===========================================================================


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(maximum, value),
    )


def distance_m(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> float:
    """
    Fast Haversine distance.

    Accurate enough for typical UAV mission segment distances and
    significantly cheaper than repeatedly using geopy.geodesic().
    """

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)

    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = (
        sin(delta_lat / 2.0) ** 2
        + cos(lat1_rad)
        * cos(lat2_rad)
        * sin(delta_lon / 2.0) ** 2
    )

    c = 2.0 * atan2(
        sqrt(a),
        sqrt(1.0 - a),
    )

    return EARTH_RADIUS_M * c


# ===========================================================================
# Provider metadata
# ===========================================================================


def provider_horizontal_resolution(
    provider,
) -> float:
    """
    Read nominal horizontal DEM resolution from provider.

    Recommended provider property:

        horizontal_resolution_m = 30.0

    etc.
    """

    resolution = getattr(
        provider,
        "horizontal_resolution_m",
        None,
    )

    if resolution is None:
        return DEFAULT_HORIZONTAL_RESOLUTION_M

    return max(
        1.0,
        float(resolution),
    )


def provider_vertical_accuracy(
    provider,
) -> float:
    """
    Read approximate vertical accuracy from provider.

    Recommended provider property:

        vertical_accuracy_m = 3.0
    """

    accuracy = getattr(
        provider,
        "vertical_accuracy_m",
        None,
    )

    if accuracy is None:
        return DEFAULT_VERTICAL_ACCURACY_M

    return max(
        0.0,
        float(accuracy),
    )


def sampling_spacing(
    provider,
) -> float:
    """
    Maximum gap between elevation samples.

    Derived automatically from the elevation provider.
    """

    resolution = provider_horizontal_resolution(
        provider
    )

    return clamp(
        resolution * SAMPLING_RESOLUTION_FACTOR,
        MIN_SAMPLING_SPACING_M,
        MAX_SAMPLING_SPACING_M,
    )


# ===========================================================================
# Simplification tolerances
# ===========================================================================


def below_target_tolerance(
    provider,
) -> float:
    """
    How far below the desired terrain-following altitude the simplified
    trajectory is allowed to go.

    Vertical accuracy is taken into account automatically.
    """

    accuracy = provider_vertical_accuracy(
        provider
    )

    return max(
        MIN_BELOW_TARGET_TOLERANCE_M,
        accuracy,
    )


def above_target_tolerance(
    provider,
    nominal_agl: float,
) -> float:
    """
    Being above the terrain-following target is generally much less
    critical than being below it.

    Allowing some extra height over valleys reduces the number of
    generated waypoints substantially.
    """

    accuracy = provider_vertical_accuracy(
        provider
    )

    agl_component = nominal_agl * 0.08

    return max(
        accuracy,
        clamp(
            agl_component,
            MIN_ABOVE_TARGET_TOLERANCE_M,
            MAX_ABOVE_TARGET_TOLERANCE_M,
        ),
    )


# ===========================================================================
# Sampling
# ===========================================================================


def interpolate_point(
    start: TerrainPoint,
    end: TerrainPoint,
    fraction: float,
    source_waypoint_index: int,
) -> TerrainPoint:
    return TerrainPoint(
        lon=(
            start.lon
            + (
                end.lon
                - start.lon
            )
            * fraction
        ),
        lat=(
            start.lat
            + (
                end.lat
                - start.lat
            )
            * fraction
        ),
        original_alt=(
            start.original_alt
            + (
                end.original_alt
                - start.original_alt
            )
            * fraction
        ),
        fraction=fraction,
        is_original=False,
        source_waypoint_index=source_waypoint_index,
    )


def sample_segment(
    start: TerrainPoint,
    end: TerrainPoint,
    provider,
    source_waypoint_index: int,
) -> list[TerrainPoint]:
    """
    Create terrain candidate points between two original waypoints.

    The number of points is determined automatically from terrain
    provider resolution.

    Purely vertical movements generate no intermediate samples.
    """

    segment_distance = distance_m(
        start.lon,
        start.lat,
        end.lon,
        end.lat,
    )

    # Pure vertical movement.
    if segment_distance < 0.01:
        return []

    spacing = sampling_spacing(
        provider
    )

    interval_count = max(
        1,
        ceil(
            segment_distance
            / spacing
        ),
    )

    if interval_count <= 1:
        return []

    return [
        interpolate_point(
            start=start,
            end=end,
            fraction=(
                i / interval_count
            ),
            source_waypoint_index=source_waypoint_index,
        )
        for i in range(
            1,
            interval_count,
        )
    ]


# ===========================================================================
# Minimum-waypoint optimization
# ===========================================================================


def is_valid_direct_segment(
    points: list[TerrainPoint],
    start_index: int,
    end_index: int,
    max_below_error: float,
    max_above_error: float,
) -> bool:
    """
    Check whether points[start_index] can connect directly to
    points[end_index] while respecting the altitude-error constraints
    at every sampled terrain point in between.

    Returns True if every intermediate sample remains within the
    allowed vertical envelope.
    """

    if end_index <= start_index + 1:
        return True

    start = points[start_index]
    end = points[end_index]

    if (
        start.adjusted_alt is None
        or end.adjusted_alt is None
    ):
        raise RuntimeError(
            "Adjusted altitude missing."
        )

    fraction_range = (
        end.fraction
        - start.fraction
    )

    if fraction_range <= 0:
        return True

    for index in range(
        start_index + 1,
        end_index,
    ):
        point = points[index]

        if point.adjusted_alt is None:
            raise RuntimeError(
                "Adjusted altitude missing."
            )

        local_fraction = (
            point.fraction
            - start.fraction
        ) / fraction_range

        flight_alt = (
            start.adjusted_alt
            + (
                end.adjusted_alt
                - start.adjusted_alt
            )
            * local_fraction
        )

        # Positive:
        # simplified flight path is above desired terrain-following path.
        #
        # Negative:
        # simplified flight path is below desired path.
        error = (
            flight_alt
            - point.adjusted_alt
        )

        # Too low -> reject immediately.
        if error < -max_below_error:
            return False

        # Too high -> also reject, but this tolerance is intentionally larger.
        if error > max_above_error:
            return False

    return True


def minimize_segment_waypoints(
    points: list[TerrainPoint],
    max_below_error: float,
    max_above_error: float,
) -> list[TerrainPoint]:
    """
    Find the minimum number of points required to represent this
    terrain-following segment.

    This is a shortest-path / dynamic-programming solution.

    Unlike greedy Douglas-Peucker simplification, this finds the actual
    minimum waypoint count for the sampled candidate profile.
    """

    n = len(points)

    if n <= 2:
        return points

    infinity = n + 1

    # dp[j]:
    # minimum number of edges required to reach point j.
    dp = [
        infinity
        for _ in range(n)
    ]

    previous: list[
        int | None
    ] = [
        None
        for _ in range(n)
    ]

    dp[0] = 0

    for end_index in range(
        1,
        n,
    ):
        # Try longer jumps first.
        #
        # This does not change correctness, but often lets us establish
        # a good solution early.
        for start_index in range(
            end_index - 1,
            -1,
            -1,
        ):
            if dp[start_index] == infinity:
                continue

            candidate_cost = (
                dp[start_index]
                + 1
            )

            # If we already have an equally good or better path,
            # skip the expensive validation.
            if candidate_cost >= dp[
                end_index
            ]:
                continue

            if not is_valid_direct_segment(
                points=points,
                start_index=start_index,
                end_index=end_index,
                max_below_error=max_below_error,
                max_above_error=max_above_error,
            ):
                continue

            dp[end_index] = (
                candidate_cost
            )

            previous[end_index] = (
                start_index
            )

    if previous[-1] is None:
        # Should normally be impossible because adjacent points are
        # always valid, but this keeps the function defensive.
        return points

    selected_indexes = []

    current_index: int | None = (
        n - 1
    )

    while current_index is not None:
        selected_indexes.append(
            current_index
        )

        current_index = previous[
            current_index
        ]

    selected_indexes.reverse()

    return [
        points[index]
        for index in selected_indexes
    ]


# ===========================================================================
# Main algorithm
# ===========================================================================


def adjust_trajectory_to_terrain(
    trajectory: list[dict[str, Any]],
    reference_point: dict[str, Any],
    provider,
    max_waypoints: int | None = None,
) -> list[dict[str, Any]]:
    """
    Adjust a UAV trajectory to terrain while attempting to produce
    the minimum possible number of waypoints.

    ------------------------------------------------------------------
    Expected coordinate convention
    ------------------------------------------------------------------

        [longitude, latitude, altitude]

    reference_point:

        {
            "type": "Point",
            "coordinates": [lon, lat, alt]
        }

    ------------------------------------------------------------------
    Algorithm
    ------------------------------------------------------------------

    1. Convert original waypoints.
    2. Generate terrain samples automatically according to provider
       resolution.
    3. Query all elevations fresh.
    4. Compute desired terrain-following altitude for every candidate.
    5. For each original waypoint pair:
         - test all possible direct waypoint jumps;
         - use dynamic programming to find the minimum-point solution.
    6. Preserve every original waypoint.
    7. Optionally enforce a maximum drone waypoint count.

    ------------------------------------------------------------------
    Provider API
    ------------------------------------------------------------------

    Required:

        provider.get_elevations(
            [(lat, lon), ...]
        ) -> list[float]

    Recommended:

        provider.horizontal_resolution_m
        provider.vertical_accuracy_m

    ------------------------------------------------------------------
    Important
    ------------------------------------------------------------------

    The "minimum" guarantee applies to the terrain points that were
    sampled from the elevation provider.

    No finite sampling algorithm can guarantee detection of terrain
    features smaller than the underlying DEM/source resolution.
    """

    if not trajectory:
        return []

    # ==================================================================
    # Phase 1
    # Reference point
    # ==================================================================

    ref_lon = float(
        reference_point[
            "coordinates"
        ][0]
    )

    ref_lat = float(
        reference_point[
            "coordinates"
        ][1]
    )

    # ==================================================================
    # Phase 2
    # Original mission points
    # ==================================================================

    original_points: list[
        TerrainPoint
    ] = []

    for index, waypoint in enumerate(
        trajectory
    ):
        coordinates = waypoint[
            "position"
        ][
            "coordinates"
        ]

        lon = float(
            coordinates[0]
        )

        lat = float(
            coordinates[1]
        )

        altitude = float(
            coordinates[2]
        )

        original_points.append(
            TerrainPoint(
                lon=lon,
                lat=lat,
                original_alt=altitude,
                is_original=True,
                source_waypoint_index=index,
            )
        )

    # ==================================================================
    # Phase 3
    # Build sampled terrain profiles
    # ==================================================================

    segment_profiles: list[
        list[TerrainPoint]
    ] = []

    all_generated_points: list[
        TerrainPoint
    ] = []

    for segment_index in range(
        len(original_points) - 1
    ):
        start = original_points[
            segment_index
        ]

        end = original_points[
            segment_index + 1
        ]

        generated = sample_segment(
            start=start,
            end=end,
            provider=provider,
            source_waypoint_index=segment_index,
        )

        all_generated_points.extend(
            generated
        )

        # Use copies for segment endpoints because each segment needs
        # its own local fraction range of 0 -> 1.
        start_local = TerrainPoint(
            lon=start.lon,
            lat=start.lat,
            original_alt=(
                start.original_alt
            ),
            is_original=True,
            source_waypoint_index=(
                start.source_waypoint_index
            ),
            fraction=0.0,
        )

        end_local = TerrainPoint(
            lon=end.lon,
            lat=end.lat,
            original_alt=(
                end.original_alt
            ),
            is_original=True,
            source_waypoint_index=(
                end.source_waypoint_index
            ),
            fraction=1.0,
        )

        segment_profiles.append(
            [
                start_local,
                *generated,
                end_local,
            ]
        )

    # ==================================================================
    # Phase 4
    # Build one fresh logical elevation request
    # ==================================================================

    coordinates_to_query: list[
        tuple[float, float]
    ] = []

    # Reference point first.
    coordinates_to_query.append(
        (
            ref_lat,
            ref_lon,
        )
    )

    # Then original points.
    for point in original_points:
        coordinates_to_query.append(
            (
                point.lat,
                point.lon,
            )
        )

    # Then all generated samples.
    for point in all_generated_points:
        coordinates_to_query.append(
            (
                point.lat,
                point.lon,
            )
        )

    elevations = provider.get_elevations(
        coordinates_to_query
    )

    if not elevations:
        return trajectory

    expected_count = len(
        coordinates_to_query
    )

    if len(elevations) != expected_count:
        raise RuntimeError(
            "Elevation provider returned "
            f"{len(elevations)} elevations "
            f"for {expected_count} requested points."
        )

    # ==================================================================
    # Phase 5
    # Assign returned elevations
    # ==================================================================

    elevation_index = 0

    ref_ground_elev = float(
        elevations[
            elevation_index
        ]
    )

    elevation_index += 1

    for point in original_points:
        point.ground_elev = float(
            elevations[
                elevation_index
            ]
        )

        elevation_index += 1

    for point in all_generated_points:
        point.ground_elev = float(
            elevations[
                elevation_index
            ]
        )

        elevation_index += 1

    # ==================================================================
    # Phase 6
    # Copy endpoint elevations into local segment profiles
    # ==================================================================

    for segment_index, profile in enumerate(
        segment_profiles
    ):
        start_original = (
            original_points[
                segment_index
            ]
        )

        end_original = (
            original_points[
                segment_index + 1
            ]
        )

        profile[
            0
        ].ground_elev = (
            start_original.ground_elev
        )

        profile[
            -1
        ].ground_elev = (
            end_original.ground_elev
        )

    # ==================================================================
    # Phase 7
    # Calculate terrain-adjusted altitude for every candidate
    # ==================================================================

    for point in original_points:
        if point.ground_elev is None:
            raise RuntimeError(
                "Missing ground elevation."
            )

        terrain_delta = (
            point.ground_elev
            - ref_ground_elev
        )

        point.adjusted_alt = (
            point.original_alt
            + terrain_delta
        )

    for profile in segment_profiles:
        for point in profile:
            if point.ground_elev is None:
                raise RuntimeError(
                    "Missing ground elevation."
                )

            terrain_delta = (
                point.ground_elev
                - ref_ground_elev
            )

            point.adjusted_alt = (
                point.original_alt
                + terrain_delta
            )

    # ==================================================================
    # Phase 8
    # Automatic optimization tolerances
    # ==================================================================

    airborne_altitudes = [
        point.original_alt
        for point in original_points
        if point.original_alt > 0
    ]

    if airborne_altitudes:
        nominal_agl = (
            sum(
                airborne_altitudes
            )
            / len(
                airborne_altitudes
            )
        )
    else:
        nominal_agl = 30.0

    max_below_error = (
        below_target_tolerance(
            provider
        )
    )

    max_above_error = (
        above_target_tolerance(
            provider,
            nominal_agl,
        )
    )

    # ==================================================================
    # Phase 9
    # Find globally minimum waypoint count PER ORIGINAL SEGMENT
    # ==================================================================

    minimized_segments: list[
        list[TerrainPoint]
    ] = []

    for profile in segment_profiles:
        minimized = (
            minimize_segment_waypoints(
                points=profile,
                max_below_error=(
                    max_below_error
                ),
                max_above_error=(
                    max_above_error
                ),
            )
        )

        minimized_segments.append(
            minimized
        )

    # ==================================================================
    # Phase 10
    # Merge segments
    # ==================================================================

    optimized_path: list[
        TerrainPoint
    ] = []

    if len(original_points) == 1:
        point = original_points[0]

        if point.adjusted_alt is None:
            raise RuntimeError(
                "Adjusted altitude missing."
            )

        optimized_path.append(
            point
        )

    else:
        for segment_index, segment in enumerate(
            minimized_segments
        ):
            if segment_index == 0:
                optimized_path.extend(
                    segment
                )
            else:
                # Don't duplicate the original waypoint where two
                # segments meet.
                optimized_path.extend(
                    segment[1:]
                )

    # ==================================================================
    # Phase 11
    # Build final mission
    # ==================================================================

    result: list[
        dict[str, Any]
    ] = []

    for point in optimized_path:
        if point.adjusted_alt is None:
            raise RuntimeError(
                "Adjusted altitude missing."
            )

        altitude = round(
            point.adjusted_alt,
            2,
        )

        if point.is_original:
            source_index = (
                point.source_waypoint_index
            )

            if source_index is None:
                raise RuntimeError(
                    "Original point missing "
                    "source waypoint index."
                )

            source = trajectory[
                source_index
            ]

            result.append(
                {
                    **source,
                    "position": {
                        **source[
                            "position"
                        ],
                        "coordinates": [
                            point.lon,
                            point.lat,
                            altitude,
                        ],
                    },
                }
            )

        else:
            source_index = (
                point.source_waypoint_index
            )

            if source_index is None:
                source_index = 0

            source = trajectory[
                source_index
            ]

            waypoint: dict[
                str,
                Any,
            ] = {
                "sequenceIndex": (
                    source.get(
                        "sequenceIndex"
                    )
                ),
                "position": {
                    "coordinates": [
                        point.lon,
                        point.lat,
                        altitude,
                    ]
                },
            }

            # Preserve role if your real mission contains one.
            if "role" in source:
                waypoint[
                    "role"
                ] = source[
                    "role"
                ]

            # Do NOT duplicate original waypoint actions onto generated
            # terrain-following points.
            if "actions" in source:
                waypoint[
                    "actions"
                ] = []

            if (
                "type"
                in source.get(
                    "position",
                    {},
                )
            ):
                waypoint[
                    "position"
                ][
                    "type"
                ] = source[
                    "position"
                ][
                    "type"
                ]

            result.append(
                waypoint
            )

    # ==================================================================
    # Phase 12
    # Re-index sequenceIndex
    #
    # Usually much safer after inserting generated waypoints.
    # ==================================================================

    for index, waypoint in enumerate(
        result
    ):
        waypoint[
            "sequenceIndex"
        ] = index

    # ==================================================================
    # Phase 13
    # Drone waypoint limit
    # ==================================================================

    if (
        max_waypoints is not None
        and len(result) > max_waypoints
    ):
        raise ValueError(
            "Terrain-following mission requires "
            f"{len(result)} waypoints, but the drone "
            f"supports only {max_waypoints}. "
            "Reducing it further would violate the "
            "configured terrain-following tolerances."
        )

    return result

if __name__ == "__main__":
    # Define Home (Takeoff location)
    home = {'type': 'Point', 'coordinates': [22.9970623, 40.57353, 0]}

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
    )

    print(f"Original Waypoints: {len(mission)}")
    print(f"Terrain Following Waypoints: {len(result)}")

    for wp in result:
        print(
            f"Lat: {wp['position']['coordinates'][1]:.5f} | Alt: {wp['position']['coordinates'][2]}m (Ground: {wp.get('ground_elev', 0)}m)")
