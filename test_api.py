import os
import requests
import json

# Base URL where your Flask app is running
BASE_URL = "http://127.0.0.1:5000"
RESOURCES_DIR = "resources"

# Map the JSON filenames to their corresponding API endpoints
TEST_CASES = {
    "time_input.json": "/api/flight-time",
    "polygon_input.json": "/api/area/polygon",
    "circle_input.json": "/api/area/circle",
    "camera_input_fov.json": "/api/camera",
    "camera_input_sensor.json": "/api/camera",
    "altitude_input.json": "/api/adjust-altitude",
    "weather_input.json": "/api/weather-filter",
    "transitions_input.json": "/api/transitions/stepped"
}


def run_tests():
    print(f"Starting API Tests against {BASE_URL}...\n" + "=" * 50)

    # Check if the resources folder exists
    if not os.path.exists(RESOURCES_DIR):
        print(f"❌ Error: The '{RESOURCES_DIR}' folder was not found.")
        return

    success_count = 0
    total_count = len(TEST_CASES)

    for filename, endpoint in TEST_CASES.items():
        filepath = os.path.join(RESOURCES_DIR, filename)
        url = f"{BASE_URL}{endpoint}"

        print(f"\nTesting Endpoint : {endpoint}")
        print(f"Using File       : {filepath}")

        # Check if the specific test file exists
        if not os.path.isfile(filepath):
            print(f"⚠️  Skipped: File '{filename}' not found in '{RESOURCES_DIR}'.")
            continue

        try:
            # Read the raw JSON string from the file
            with open(filepath, 'r') as file:
                raw_json_data = file.read()

            # Send the raw string to the API with the correct Content-Type header
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, data=raw_json_data, headers=headers)

            # Check if the request was successful
            if response.status_code == 200:
                print("✅ Status       : 200 OK")

                # Pretty-print the response JSON
                response_data = response.json()
                print("📦 Response     :")
                print(json.dumps(response_data, indent=2))
                success_count += 1
            else:
                print(f"❌ Status       : {response.status_code} FAILED")
                print(f"⚠️  Error Output : {response.text}")

        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Is the Flask server (app.py) running?")
            return  # Abort testing if server is completely unreachable
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")

    print("\n" + "=" * 50)
    print(f"Test Run Complete: {success_count}/{total_count} endpoints responded with 200 OK.")


if __name__ == "__main__":
    run_tests()