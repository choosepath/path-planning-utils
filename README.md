# Path Planning and ChoosePath Utilities - API

A Python toolkit and REST API for advanced UAV mission planning. This project provides high-precision calculations for flight time estimation, geodesic areas, photogrammetry grids, intelligent terrain-following trajectory adjustments, and weather-based fleet filtering.

## Features

* **Kinematic Flight Time Estimation**: Calculates highly accurate flight times by modeling drone acceleration, deceleration, and cornering speeds, fixing the inaccuracies of simple linear distance/speed models at high speeds.
* **Precise Area Calculations**: Uses Karney's algorithm (via `pyproj`) to calculate exact geodesic polygon areas on the WGS84 ellipsoid.
* **Photogrammetry Grid Metrics**: Calculates Ground Sampling Distance (GSD), scanning density (strip spacing), and capturing density (trigger distance) using either hardware sensor specifications or Field of View (FOV) angles.
* **Modular Terrain Following**: Automatically adjusts a 3D trajectory to safely follow ground elevation. 
    * Preserves all original mission waypoints.
    * Dynamically interpolates intermediate waypoints based on terrain changes.
    * Modular Strategy Pattern supporting both **Open-Meteo (Free)** and **Google Maps** Elevation APIs.
* **Fleet Weather Filtering**: Evaluates real-time weather at a POI to filter out drones that cannot safely operate in current temperature, wind, or precipitation conditions.

---

## Project Structure

    .
    ├── app.py                             # Main Flask application (API Routing)
    ├── serializers.py                     # JSON parsing, data formatting, and serialization
    ├── time_estimation.py                 # Kinematic flight time logic
    ├── areas.py                           # Geodesic and Cartesian area calculations
    ├── camera_related_utils.py            # Photogrammetry and GSD formulas
    ├── altitude_elevation_adjustment.py   # Terrain-following logic and API providers
    ├── weather_filtering.py               # Fleet filtering based on OpenWeatherMap data
    ├── test_api.py                        # Automated testing script
    ├── transitioning_waypoints.py         # Generates transitioning stepped trajectories between two points
    ├── Dockerfile                         # Containerization instructions using Python 3.11
    ├── requirements.txt                   # Python dependencies (Flask, geopy, pyproj, requests, python-dotenv)
    ├── .env                               # Environment variables (API keys)
    └── resources/                         # Directory containing JSON test payloads
        ├── transitioning_input.json
        ├── time_input.json
        ├── polygon_input.json
        ├── circle_input.json
        ├── camera_input_fov.json
        ├── camera_input_sensor.json
        ├── altitude_input.json
        └── weather_input.json

---

## Running with Docker (Recommended)

The easiest way to run the API is via Docker.

**1. Build the Docker Image**
Navigate to the project root and run:
bash
docker build -t uav-api .

*(Note: The Dockerfile uses `python:3.11` and installs `proj-bin` to ensure the `pyproj` geospatial library compiles correctly).*

**2. Run the Container**
Start the container and map port 5000 to your local machine:
bash
docker run -p 5000:5000 uav-api

The API is now live at `http://localhost:5000`.

---

## Local Installation & Setup (Without Docker)

1. **Clone the repository** and navigate to the project folder.
2. **Install the required dependencies**:
   bash
   pip install -r requirements.txt
   
3. **Configure API Keys**: Create a `.env` file in the root directory to store your private keys securely.
   text
   GOOGLE_API_KEY=your_google_maps_key_here
   OPENWEATHER_API_KEY=your_openweather_key_here
   
4. **Run the API**:
   bash
   python app.py
   

---

## Testing

The project includes an automated testing script that reads the JSON files from the `resources/` folder and fires them against the running API.

1. Ensure `app.py` is running (either locally or via Docker).
2. Open a second terminal and run:
   bash
   python test_api.py
   
This will output the HTTP status codes and the formatted JSON responses from the server.

---

## API Endpoints Reference

All endpoints expect a `POST` request with an `application/json` Content-Type.

### 1. Flight Time Estimation (`/api/flight-time`)

Estimates flight time using acceleration and cornering kinematics.
* **Payload**:
  ```json
  {
    "waypoints": [
      [37.9838, 23.7275, 50],
      [37.9847, 23.7275, 50],
      [37.9847, 23.7286, 50],
      [37.9838, 23.7286, 50]
    ],
    "max_speed": 10.0,
    "accel": 2.5,
    "min_turn_speed": 1.0
  }
  
  *(Reference: `time_input.json`)*

### 2. Area Calculations (`/api/area/polygon` & `/api/area/circle`)

Calculates the area of WGS84 coordinates in square meters and hectares.
* **Polygon Payload**:
  ```json
  {
    "waypoints": [
      [37.9838, 23.7275],
      [37.9847, 23.7275],
      [37.9847, 23.7286],
      [37.9838, 23.7286]
    ]
  }
  
  *(Reference: `polygon_input.json`)*
* **Circle Payload**: 
  json
  { 
    "radius": 150.5 
  }
  

### 3. Photogrammetry Metrics (`/api/camera`)

Calculates GSD and grid spacing. Accepts either exact Sensor specs OR FOV angles.
* **Payload (Sensor Method)**:
  ```json
  {
    "altitude": 60,
    "sensor_w": 13.2,
    "sensor_h": 8.8,
    "focal_length": 8.8,
    "img_w": 5472,
    "img_h": 3648,
    "sidelap": 70,
    "frontlap": 80
  }
  
  *(Reference: `camera_input_sensor.json`)*
* **Payload (FOV Method)**: 
  *(Reference: `camera_input_fov.json`)*

### 4. Terrain Following (`/api/adjust-altitude`)

Densifies a trajectory and adjusts altitudes to maintain constant AGL over terrain.
* **Payload**:
  ```json
  {
    "trajectory": [
      {"lat": 40.57353, "lon": 22.9970623, "alt": 60},
      {"lat": 40.580472, "lon": 22.9977901, "alt": 60}
    ],
    "reference_point": {
      "lat": 40.57353,
      "lon": 22.9970623,
      "alt": 0
    },
    "provider": "google",
    "interpolation_step": 10,
    "vertical_step": 3
  }
  
  *(Reference: `altitude_input.json`)*
  *(Note: Set `"provider": "open-meteo"` to use the free Open-Meteo API instead of Google Maps).*

### 5. Fleet Weather Filtering (`/api/weather-filter`)

Evaluates current, real-time weather conditions at a specific Location (POI) using OpenWeatherMap, and filters a provided list of drones to return only those capable of surviving the conditions. 
* **Filters applied**:
    * Operational temperature ranges (`temp_range_c`).
    * Maximum wind resistance (`max_wind_ms`).
    * Minimum required IP (Ingress Protection) rating mapped dynamically to precipitation intensity (mm/h).
* **Payload**:
  ```json
  {
    "poi": {
      "lat": 40.57353,
      "lon": 22.9970623
    },
    "vehicles": [
      {
        "id": "DJI_Mavic_3_Enterprise",
        "temp_range_c": [-10, 40],
        "max_wind_ms": 12.0,
        "ip_rating": "IP43"
      },
      {
        "id": "DJI_Matrice_300_RTK",
        "temp_range_c": [-20, 50],
        "max_wind_ms": 15.0,
        "ip_rating": "IP45"
      }
    ]
  }
  
  *(Reference: `weather_input.json`)*
  *(Note: Requires `OPENWEATHER_API_KEY` to be set in your `.env` file).*
  
### 6. Stepped-Altitude Transitions (`/api/transitions/stepped`)

Generates a safe connecting transition between two points using a Manhattan-style stepped routing method. Forces the UAV to ascend or descend vertically to a safe cruising altitude, transit horizontally, and then transition vertically to the target. Includes offset parameters for swarm deconfliction.
* **Payload**:
  ```json
  {
    "start_point": {"lat": 44.25, "lon": 28.35, "alt": 5},
    "end_point": {"lat": 44.32, "lon": 28.60, "alt": 60},
    "offset_level": 1,
    "offset_step": 5.0,
    "transitioning_altitude": 100
  }
  
  *(Reference: transitions_input.json)
  *(Note: offset_level determines the altitude tier (0, 1, 2, etc.), and offset_step is the vertical separation between tiers in meters. transitioning_altitude is optional; if omitted, the system defaults to the highest altitude of the two points).