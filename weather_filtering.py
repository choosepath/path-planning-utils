import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# -------------------------
# Precipitation to IP Mapping
# -------------------------
def get_minimum_water_ip(precip_mmh):
    """Maps precipitation intensity (mm/h) to a minimum required IP water rating (0-9)."""
    if precip_mmh == 0:
        return 0  # No rain
    elif precip_mmh <= 2.5:
        return 3  # Light rain -> IPx3
    elif precip_mmh <= 10.0:
        return 4  # Moderate rain -> IPx4
    elif precip_mmh <= 50.0:
        return 5  # Heavy rain -> IPx5
    else:
        return 6  # Violent storm -> IPx6


# -------------------------
# Weather fetching function
# -------------------------
def fetch_weather(api_key, lat, lon):
    """Fetch current weather from OpenWeatherMap."""
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"

    try:
        response = requests.get(url).json()
        if response.get("cod") != 200:
            raise ValueError(response.get("message", "Unknown API error"))

        rain_mmh = response.get("rain", {}).get("1h", 0.0)
        snow_mmh = response.get("snow", {}).get("1h", 0.0)

        return {
            "precip_total": rain_mmh + snow_mmh,
            "wind_ms": response.get("wind", {}).get("speed", 0.0),
            "temp_c": response.get("main", {}).get("temp", 20.0)
        }
    except Exception as e:
        raise RuntimeError(f"OpenWeatherMap API failed: {e}")


# -------------------------
# Vehicle filtering function
# -------------------------
def is_vehicle_suitable(vehicle, weather):
    # 1. Check Temperature
    temp_min, temp_max = vehicle.get("temp_range_c", [-20, 50])
    if not (temp_min <= weather["temp_c"] <= temp_max):
        return False

    # 2. Check Wind Resistance
    max_wind = vehicle.get("max_wind_ms", 0)
    if weather["wind_ms"] > max_wind:
        return False

    # 3. Check IP Rating
    ip_string = vehicle.get("ip_rating", "IP00").upper()
    try:
        vehicle_water_rating = int(ip_string[3]) if len(ip_string) >= 4 else 0
    except ValueError:
        vehicle_water_rating = 0

    required_water_rating = get_minimum_water_ip(weather["precip_total"])

    if vehicle_water_rating < required_water_rating:
        return False

    return True


# -------------------------
# Core API Logic
# -------------------------
def filter_fleet_for_mission(lat, lon, vehicles):
    """
    Main function called by the API.
    Accepts latitude, longitude, and a list of vehicle dictionaries.
    """
    api_key = os.getenv('OPENWEATHER_API_KEY')
    if not api_key:
        raise ValueError("OPENWEATHER_API_KEY is not set in the .env file.")

    weather = fetch_weather(api_key, lat, lon)
    suitable_list = [v for v in vehicles if is_vehicle_suitable(v, weather)]

    return {
        "poi": {"lat": lat, "lon": lon},
        "weather_conditions": weather,
        "suitable_vehicles": [v["id"] for v in suitable_list]
    }


# -------------------------
# Example usage (Local Testing)
# -------------------------
if __name__ == "__main__":
    import json

    # 1. Define test coordinates (Thessaloniki)
    test_lat = 40.57353
    test_lon = 22.9970623

    # 2. Define a sample fleet
    test_vehicles = [
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
        },
        {
            "id": "Custom_Heavy_Lifter",
            "temp_range_c": [0, 30],
            "max_wind_ms": 5.0,
            "ip_rating": "IP00"
        }
    ]

    print(f"🌍 Running local weather test for coordinates: {test_lat}, {test_lon}...")

    try:
        # Run the core function
        result = filter_fleet_for_mission(test_lat, test_lon, test_vehicles)

        print("\n✅ Filter Results:")
        print(json.dumps(result, indent=4))
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")