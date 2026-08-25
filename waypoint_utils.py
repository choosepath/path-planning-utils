def transform_waypoints_to_trajectory(path):
    if not path:
        return []

    waypoints = path.get("waypoints", [])

    def get_point(waypoint): return waypoint.get("position", {}).get("coordinates", [
        None]) if waypoint.get("position") else waypoint["point"]["coordinates"]

    return [
        {
            "lon": get_point(waypoint)[0],
            "lat": get_point(waypoint)[1],
            "alt": get_point(waypoint)[2] if waypoint.get("position") else waypoint["altitude"],
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
                        point.get("lon", 0),
                        point.get("lat", 0),
                    ],
                },
                "position": {
                    "type": "Point",
                    "coordinates": [
                        point.get("lon", 0),
                        point.get("lat", 0),
                        point.get("alt", 0),
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


def point_to_lat_lon(point):
    return {
        "lon": point["coordinates"][0],
        "lat": point["coordinates"][1],
        "alt": point["coordinates"][2] if len(point["coordinates"]) > 2 else 0,
    }
