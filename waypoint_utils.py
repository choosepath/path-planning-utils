def transform_waypoints_to_trajectory(path):
    if not path:
        return []

    waypoints = path.get("waypoints", [])

    return [
        {
            "lon": waypoint["point"]["coordinates"][0],
            "lat": waypoint["point"]["coordinates"][1],
            "alt": waypoint["altitude"],
        }
        for waypoint in waypoints
    ]

def transform_trajectory_to_waypoints(trajectory):
    return {
        "waypoints": [
            {
                "point": {
                    "type": "Point",
                    "coordinates": [
                        point["lon"],
                        point["lat"],
                    ],
                },
                "altitude": point.get("alt", 0),
            }
            for point in trajectory
        ],
    }

def coordinates_array_to_lat_lon(coordinates):
    return {
        "lon": coordinates[0],
        "lat": coordinates[1],
        "alt": coordinates[2],
    }