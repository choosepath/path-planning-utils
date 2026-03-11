import math

def estimate_uav_flight_time(waypoints, max_speed, accel=2.0, min_turn_speed=1.0):

    """
    Estimates flight time for a quadcopter using a kinematic segment model.

    Args:
        waypoints: List of tuples [(lat, lon, alt), ...] or [(lat, lon), ...]
                   (Alt is optional, defaults to 0 if not provided)
        max_speed: Cruise speed in m/s (target speed for straight lines)
        accel:     Drone acceleration/deceleration in m/s^2 (Standard DJI/Px4 is ~2.0 to 4.0)
        min_turn_speed: Minimum speed the drone maintains at a sharp turn (m/s)

    Returns:
        float: Estimated total time in minutes
    """

    """
    Acceleration suggested values for  DJI drones:
        Cine / Tripod  |	All Models         |	1.0 m/s²       |	Slow, smooth filming. High precision close to obstacles.
        Normal (P-GPS) |	Mavic / Air / Mini |	2.0 - 2.5 m/s² |	Standard mapping missions, waypoint flights, inspection.
        Normal (P-GPS) |	Matrice / Inspire  |	1.5 - 2.0 m/s² |	Heavy enterprise payloads (LiDAR/Zoom cameras) where braking is slower.
        Sport (S-Mode) |	Mavic / Air / Mini |	5.0 - 6.0 m/s² |	High-speed transit, chasing moving subjects.
        Sport (S-Mode) |	Matrice / Inspire  |	4.0 m/s²       |	Urgent response tasks (Search & Rescue).
    """

    # --- Helper: Convert WGS84 to Local Cartesian (Meters) ---
    # Uses a flat-earth approximation relative to the first waypoint.
    # sufficiently accurate for drone trajectories < 50km.

    R_EARTH = 6378137.0  # Earth radius in meters
    origin = waypoints[0]
    local_points = []

    for wp in waypoints:
        lat, lon = wp[0], wp[1]
        alt = wp[2] if len(wp) > 2 else 0

        # Convert degrees to radians
        d_lat = math.radians(lat - origin[0])
        d_lon = math.radians(lon - origin[1])
        lat_avg = math.radians((lat + origin[0]) / 2.0)

        # Flat earth projection
        x = d_lon * R_EARTH * math.cos(lat_avg)
        y = d_lat * R_EARTH
        z = alt
        local_points.append((x, y, z))

    # --- Step 1: Calculate "Cornering Speeds" ---
    # The drone must slow down at sharp turns.
    # We calculate the max speed allowed at each vertex based on the angle.

    n = len(local_points)
    corner_speeds = [0.0] * n  # Start and End are always 0 speed

    for i in range(1, n - 1):
        # Get vectors for previous segment and next segment
        p_prev = local_points[i - 1]
        p_curr = local_points[i]
        p_next = local_points[i + 1]

        # Vector A (entering turn) and Vector B (exiting turn)
        vec_in = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1], p_curr[2] - p_prev[2])
        vec_out = (p_next[0] - p_curr[0], p_next[1] - p_curr[1], p_next[2] - p_curr[2])

        # Calculate magnitudes
        mag_in = math.sqrt(sum(c ** 2 for c in vec_in))
        mag_out = math.sqrt(sum(c ** 2 for c in vec_out))

        if mag_in == 0 or mag_out == 0:
            corner_speeds[i] = 0
            continue

        # Dot product to find angle
        dot = sum(a * b for a, b in zip(vec_in, vec_out))
        # Clamp value to avoid domain errors
        cos_theta = max(-1.0, min(1.0, dot / (mag_in * mag_out)))

        # Angle of the turn (0 = straight line, 180 = U-turn)
        # Note: We actually want the deviation angle.
        # If dot product is 1 (straight), we don't slow down.
        # We can use a heuristic: Speed scales with cos(deviation_angle / 2)

        # Simple Heuristic:
        # Straight line (cos_theta=1) -> Factor 1.0
        # 90 deg turn (cos_theta=0) -> Factor ~0.7
        # 180 deg U-turn (cos_theta=-1) -> Factor 0.0

        # Map cos_theta (-1 to 1) to a speed factor (0 to 1)
        # Using Half-Angle formula logic for smooth falloff
        turn_factor = math.sqrt((1 + cos_theta) / 2)

        target_v = max_speed * turn_factor
        corner_speeds[i] = max(min_turn_speed, target_v)

    # --- Step 2: Calculate Kinematics per Segment ---
    total_time = 0.0

    for i in range(n - 1):
        p1 = local_points[i]
        p2 = local_points[i + 1]

        dist = math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2)

        v_start = corner_speeds[i]
        v_end = corner_speeds[i + 1]

        # Physics: Distance required to accelerate from v_start to max_speed
        d_acc = (max_speed ** 2 - v_start ** 2) / (2 * accel)

        # Physics: Distance required to decelerate from max_speed to v_end
        d_dec = (max_speed ** 2 - v_end ** 2) / (2 * accel)

        if dist >= (d_acc + d_dec):
            # Scenario A: The segment is long enough to reach full speed (Trapezoidal Profile)
            t_acc = (max_speed - v_start) / accel
            t_dec = (max_speed - v_end) / accel

            d_cruise = dist - (d_acc + d_dec)
            t_cruise = d_cruise / max_speed

            total_time += (t_acc + t_cruise + t_dec)

        else:
            # Scenario B: Segment is too short, drone never reaches max_speed (Triangular Profile)
            # It accelerates to a peak, then immediately decelerates
            # Solve for v_peak: 2*a*d = (v_peak^2 - v_start^2) + (v_peak^2 - v_end^2)

            v_peak_sq = (2 * accel * dist + v_start ** 2 + v_end ** 2) / 2
            v_peak = math.sqrt(v_peak_sq)

            t_acc = (v_peak - v_start) / accel
            t_dec = (v_peak - v_end) / accel

            total_time += (t_acc + t_dec)

    return total_time/60

if __name__ == '__main__':

    # Define Waypoints (Lat, Lon, Alt_meters)
    # This approximates a square path of roughly 100m sides
    mission_route = [
        (37.9838, 23.7275, 50),  # Start
        (37.9847, 23.7275, 50),  # Point B (~100m North)
        (37.9847, 23.7286, 50),  # Point C (~100m East)
        (37.9838, 23.7286, 50),  # Point D (~100m South)
        (37.9838, 23.7275, 50)  # Return to Start
    ]

    # Case 1: Low speed (Your old model would likely work here)
    time_slow = estimate_uav_flight_time(mission_route, max_speed=3.0)

    # Case 2: High speed (Requires this kinematic model)
    # Notice we assume acceleration of 3 m/s^2 (typical for sport mode)
    time_fast = estimate_uav_flight_time(mission_route, max_speed=15.0, accel=3.0)

    print(f"Time @ 3m/s: {time_slow:.1f} minutes")
    print(f"Time @ 15m/s: {time_fast:.1f} minutes")