from flask import Flask, request, Response
import json
import serializers

app = Flask(__name__)

def create_json_response(json_string, status=200):
    """Helper to return raw JSON strings as proper Flask HTTP responses."""
    return Response(json_string, status=status, mimetype='application/json')

@app.route('/api/flight-time', methods=['POST'])
def flight_time_endpoint():
    try:
        raw_json = request.get_data(as_text=True)
        result_json = serializers.process_time_estimation(raw_json)
        return create_json_response(result_json)
    except Exception as e:
        return create_json_response(json.dumps({"error": str(e)}), 400)

@app.route('/api/area/polygon', methods=['POST'])
def polygon_area_endpoint():
    try:
        raw_json = request.get_data(as_text=True)
        result_json = serializers.process_polygon_area(raw_json)
        return create_json_response(result_json)
    except Exception as e:
        return create_json_response(json.dumps({"error": str(e)}), 400)

@app.route('/api/area/circle', methods=['POST'])
def circle_area_endpoint():
    try:
        raw_json = request.get_data(as_text=True)
        result_json = serializers.process_circle_area(raw_json)
        return create_json_response(result_json)
    except Exception as e:
        return create_json_response(json.dumps({"error": str(e)}), 400)

@app.route('/api/camera', methods=['POST'])
def flight_metrics_endpoint():
    try:
        raw_json = request.get_data(as_text=True)
        result_json = serializers.process_flight_metrics(raw_json)
        return create_json_response(result_json)
    except Exception as e:
        return create_json_response(json.dumps({"error": str(e)}), 400)

@app.route('/api/adjust-altitude', methods=['POST'])
def adjust_altitude_endpoint():
    try:
        raw_json = request.get_data(as_text=True)
        result_json = serializers.process_altitude_adjustment(raw_json)
        return create_json_response(result_json)
    except Exception as e:
        return create_json_response(json.dumps({"error": str(e)}), 500)

@app.route('/api/weather-filter', methods=['POST'])
def filter_fleet_endpoint():
    try:
        raw_json = request.get_data(as_text=True)
        result_json = serializers.process_fleet_filtering(raw_json)
        return create_json_response(result_json)
    except Exception as e:
        return create_json_response(json.dumps({"error": str(e)}), 400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)