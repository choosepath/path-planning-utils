def generate_connecting_trajectory(start_point, end_point, offset_level=0, offset_step=5.0,
                                   transitioning_altitude=None):
    """
    Generates a safe connecting trajectory between two points using a "stepped" routing method.
    The UAV ascends/descends vertically to a cruise altitude, transits horizontally, and descends/ascends.

    Args:
        start_point (list/tuple or dict): The origin point e.g., [lat, lon, alt]
        end_point (list/tuple or dict): The destination point e.g., [lat, lon, alt]
        offset_level (int): The altitude tier for this specific drone (0, 1, 2, ...).
        offset_step (float): The vertical separation distance between tiers in meters (default 5.0).
        transitioning_altitude (float, optional): A forced base cruising altitude.
                                                  If None, it defaults to the highest of the two points.

    Returns:
        list of dicts: The generated waypoints representing the safe trajectory.
    """

    # 1. Standardize Inputs
    if isinstance(start_point, (list, tuple)):
        lat1, lon1, alt1 = start_point
    else:
        lat1, lon1, alt1 = start_point['lat'], start_point['lon'], start_point['alt']

    if isinstance(end_point, (list, tuple)):
        lat2, lon2, alt2 = end_point
    else:
        lat2, lon2, alt2 = end_point['lat'], end_point['lon'], end_point['alt']

    # 2. Calculate Safe Cruising Altitude
    if transitioning_altitude is not None:
        base_cruise_alt = float(transitioning_altitude)
    else:
        base_cruise_alt = max(alt1, alt2)

    cruise_alt = base_cruise_alt + (offset_level * offset_step)

    trajectory = []

    # Waypoint A: Start Point
    trajectory.append({'lat': lat1, 'lon': lon1, 'alt': alt1})

    # Waypoint B: Vertical Transition to Cruise
    # Use != instead of > to allow descending to a lower transit altitude if forced by the user
    if cruise_alt != alt1:
        trajectory.append({'lat': lat1, 'lon': lon1, 'alt': cruise_alt})

    # Waypoint C: Horizontal Transit
    if lat1 != lat2 or lon1 != lon2:
        trajectory.append({'lat': lat2, 'lon': lon2, 'alt': cruise_alt})

    # Waypoint D: Vertical Transition to End
    if cruise_alt != alt2:
        trajectory.append({'lat': lat2, 'lon': lon2, 'alt': alt2})

    return trajectory


# ==========================================
# Example Usage & 3D Visualization
# ==========================================
if __name__ == '__main__':
    import json
    import matplotlib.pyplot as plt

    # Define test points
    pt_A = [44.25, 28.35, 5]
    pt_B = [44.32, 28.60, 60]

    # Test 1: Original behavior (defaults to max altitude which is 60)
    drone_0 = generate_connecting_trajectory(pt_A, pt_B, offset_level=0)

    # Test 2: Forced transitioning altitude at 100m
    drone_1 = generate_connecting_trajectory(pt_A, pt_B, offset_level=1, transitioning_altitude=100)

    print("🚁 Drone 0 Trajectory (Auto Max Alt = 60m):")
    print(json.dumps(drone_0, indent=2))

    print("\n🚁 Drone 1 Trajectory (Forced Alt = 100m + 5m Offset):")
    print(json.dumps(drone_1, indent=2))

    # --- 3D Visualization Setup ---
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')


    def plot_trajectory(trajectory, label, color, line_style='-'):
        lats = [pt['lat'] for pt in trajectory]
        lons = [pt['lon'] for pt in trajectory]
        alts = [pt['alt'] for pt in trajectory]
        ax.plot(lons, lats, alts, label=label, color=color, linestyle=line_style, linewidth=2, marker='o', markersize=6)


    plot_trajectory(drone_0, "Drone 0 (Auto 60m)", color='blue')
    plot_trajectory(drone_1, "Drone 1 (Forced 100m + Offset)", color='orange', line_style='--')

    ax.set_title('UAV Stepped-Altitude Transitions')
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_zlabel('Altitude (m)')
    ax.view_init(elev=20, azim=-45)
    ax.legend()
    plt.show()