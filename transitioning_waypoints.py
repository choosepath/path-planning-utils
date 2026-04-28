def generate_connecting_trajectory(start_point, end_point, offset_level=0, offset_step=5.0):
    """
    Generates a safe connecting trajectory between two points using a "stepped" routing method.
    The UAV ascends vertically to a safe cruising altitude, transits horizontally, and descends.

    Args:
        start_point (list/tuple or dict): The origin point e.g., [lat, lon, alt]
        end_point (list/tuple or dict): The destination point e.g., [lat, lon, alt]
        offset_level (int): The altitude tier for this specific drone (0, 1, 2, ...).
        offset_step (float): The vertical separation distance between tiers in meters (default 5.0).

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
    base_cruise_alt = max(alt1, alt2)
    cruise_alt = base_cruise_alt + (offset_level * offset_step)

    trajectory = []

    # Waypoint A: Start Point
    trajectory.append({'lat': lat1, 'lon': lon1, 'alt': alt1})

    # Waypoint B: Vertical Ascent
    if cruise_alt > alt1:
        trajectory.append({'lat': lat1, 'lon': lon1, 'alt': cruise_alt})

    # Waypoint C: Horizontal Transit
    if lat1 != lat2 or lon1 != lon2:
        trajectory.append({'lat': lat2, 'lon': lon2, 'alt': cruise_alt})

    # Waypoint D: Vertical Descent
    if cruise_alt > alt2:
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

    # Generate trajectories for 3 different drones
    drone_0 = generate_connecting_trajectory(pt_A, pt_B, offset_level=0)
    drone_1 = generate_connecting_trajectory(pt_A, pt_B, offset_level=1)
    drone_2 = generate_connecting_trajectory(pt_A, pt_B, offset_level=2)

    print("🚁 Drone 0 Trajectory (No Offset):")
    print(json.dumps(drone_0, indent=2))

    # --- 3D Visualization Setup ---
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')


    # Helper function to plot a single trajectory
    def plot_trajectory(trajectory, label, color, line_style='-'):
        lats = [pt['lat'] for pt in trajectory]
        lons = [pt['lon'] for pt in trajectory]
        alts = [pt['alt'] for pt in trajectory]

        # Plot the lines and the waypoints
        ax.plot(lons, lats, alts, label=label, color=color, linestyle=line_style, linewidth=2, marker='o', markersize=6)


    # Plot each drone
    plot_trajectory(drone_0, "Drone 0 (Base Level)", color='blue')
    plot_trajectory(drone_1, "Drone 1 (+5m Offset)", color='orange', line_style='--')
    plot_trajectory(drone_2, "Drone 2 (+10m Offset)", color='green', line_style='-.')

    # Formatting the plot
    ax.set_title('UAV Stepped-Altitude Routing (Collision Avoidance)')
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_zlabel('Altitude (m)')

    # Adjust viewing angle for better perspective
    ax.view_init(elev=20, azim=-45)

    ax.legend()
    plt.show()