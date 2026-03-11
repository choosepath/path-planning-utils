import math

def solve_via_fov(altitude, hfov_deg, vfov_deg, h_res_px, v_res_px,
                  sidelap_percent, frontlap_percent):
    """
    Implementation A: The FOV/Angle-based approach (Paper methodology).

    GSD is calculated as min(ground_width/h_res, ground_height/v_res).
    """
    # 1. Convert degrees to radians
    theta_h = math.radians(hfov_deg)
    theta_v = math.radians(vfov_deg)

    # 2. Calculate Ground Footprints (Physical dimensions on the ground)
    # Width = 2 * h * tan(theta / 2)
    ground_width = 2 * altitude * math.tan(theta_h / 2)
    ground_height = 2 * altitude * math.tan(theta_v / 2)

    # 3. Calculate Densities (Spacing)
    # Scanning Density (ds): Distance between flight lines (Side)
    ds = ground_width * (1.0 - (sidelap_percent / 100.0))

    # Capturing Density (dc): Distance between triggers (Front)
    dc = ground_height * (1.0 - (frontlap_percent / 100.0))

    # 4. Calculate GSD (User Request: min of H and V projection)
    gsd_h = ground_width / h_res_px
    gsd_v = ground_height / v_res_px

    # Note: We usually want the MAX GSD (worst resolution) for safety,
    # but I am following your specific request for MIN.
    final_gsd = min(gsd_h, gsd_v)

    return {
        "method": "FOV_Based",
        "gsd": final_gsd*100,  # cm/pixel
        "scanning_density": ds,  # Meters
        "capturing_density": dc,  # Meters
        "ground_width": ground_width,  # Meters
        "ground_height": ground_height  # Meters
    }


def solve_via_sensor(altitude, sensor_width_mm, sensor_height_mm, focal_length_mm,
                     h_res_px, v_res_px, sidelap_percent, frontlap_percent):
    """
    Implementation B: The Sensor/Optics-based approach (Photogrammetry standard).
    """
    # 1. Calculate Ground Footprints using similar triangles
    # Dimension_ground = (Dimension_sensor * Altitude) / Focal_Length
    # Units: (mm * m) / mm = meters

    ground_width = (sensor_width_mm * altitude) / focal_length_mm
    ground_height = (sensor_height_mm * altitude) / focal_length_mm

    # 2. Calculate Densities (Spacing)
    ds = ground_width * (1.0 - (sidelap_percent / 100.0))
    dc = ground_height * (1.0 - (frontlap_percent / 100.0))

    # 3. Calculate GSD
    # Standard formula: (Sensor_Width_mm * Altitude_m * 100) / (Focal_Length_mm * Image_Width_px)
    # We calculate it here in meters/pixel to match the other function
    gsd_h = ground_width / h_res_px
    gsd_v = ground_height / v_res_px

    # Modern sensors have square pixels, so gsd_h == gsd_v usually.
    final_gsd = max(gsd_h, gsd_v)

    return {
        "method": "Sensor_Based",
        "gsd": final_gsd*100,  # cm/pixel
        "scanning_density": ds,  # Meters
        "capturing_density": dc,  # Meters
        "ground_width": ground_width,  # Meters
        "ground_height": ground_height  # Meters
    }


def calculate_flight_metrics(**kwargs):
    """
    Unified Wrapper Function.
    Accepts a dictionary of arguments and routes to the correct solver.

    Common Args:
        altitude (float): Meters
        sidelap (float): Percent (0-100)
        frontlap (float): Percent (0-100)

    FOV Args (Set A):
        hfov, vfov (degrees)
        h_res, v_res (pixels)

    Sensor Args (Set B):
        sensor_w, sensor_h (mm)
        focal_length (mm)
        img_w, img_h (pixels)
    """

    # Extract common parameters
    alt = kwargs.get('altitude')
    side = kwargs.get('sidelap', 70)  # Default 70%
    front = kwargs.get('frontlap', 80)  # Default 80%

    if alt is None:
        raise ValueError("Altitude is required for both methods.")

    # --- Strategy Selection Logic ---

    # Check if we have Sensor Data (Priority 1: More Accurate)
    if all(k in kwargs for k in ['sensor_w', 'sensor_h', 'focal_length', 'img_w', 'img_h']):
        return solve_via_sensor(
            altitude=alt,
            sensor_width_mm=kwargs['sensor_w'],
            sensor_height_mm=kwargs['sensor_h'],
            focal_length_mm=kwargs['focal_length'],
            h_res_px=kwargs['img_w'],
            v_res_px=kwargs['img_h'],
            sidelap_percent=side,
            frontlap_percent=front
        )

    # Check if we have FOV Data (Priority 2: The Paper's Method)
    elif all(k in kwargs for k in ['hfov', 'vfov', 'h_res', 'v_res']):
        return solve_via_fov(
            altitude=alt,
            hfov_deg=kwargs['hfov'],
            vfov_deg=kwargs['vfov'],
            h_res_px=kwargs['h_res'],
            v_res_px=kwargs['v_res'],
            sidelap_percent=side,
            frontlap_percent=front
        )

    else:
        missing_keys = "Either (hfov, vfov, h_res, v_res) OR (sensor_w, sensor_h, focal_length, img_w, img_h)"
        raise ValueError(f"Insufficient parameters provided. Required set: {missing_keys}")

if __name__ == '__main__':

    # Case 1: Using FOV inputs (Paper Method)
    p4p_fov_inputs = {
        'altitude': 60,
        'hfov': 73.74,             # Derived from 84° Diagonal + 3:2 Aspect Ratio
        'vfov': 53.13,             # Derived from 84° Diagonal + 3:2 Aspect Ratio
        'h_res': 5472,
        'v_res': 3648,
        'sidelap_percentage': 70,
        'frontlap_percentage': 60
    }

    # Case 2: Using Sensor inputs (Pro Method - DJI Mavic 3E specs)
    p4p_sensor_inputs = {
        'altitude': 60,           # Example altitude in meters
        'sensor_w': 13.2,          # Physical Sensor Width (1-inch sensor is ~13.2mm wide)
        'sensor_h': 8.8,           # Physical Sensor Height (1-inch sensor is ~8.8mm tall)
        'focal_length': 8.8,       # REAL Focal Length (Not the "24mm equivalent")
        'img_w': 5472,             # Native Photo Resolution Width
        'img_h': 3648,             # Native Photo Resolution Height (3:2 Aspect Ratio)
        'sidelap_percentage': 70,
        'frontlap_percentage': 60
    }

    print("--- RESULTS: FOV Method ---")
    res_fov = calculate_flight_metrics(**p4p_fov_inputs)
    print(f"Method: {res_fov['method']}")
    print(f"GSD: {res_fov['gsd']:.2f} cm/px")
    print(f"Scanning Density (Strip): {res_fov['scanning_density']:.2f} m")
    print(f"Capturing Density (Trigger): {res_fov['capturing_density']:.2f} m")
    print("-" * 30)

    print("--- RESULTS: Sensor Method ---")
    res_sensor = calculate_flight_metrics(**p4p_sensor_inputs)
    print(f"Method: {res_sensor['method']}")
    print(f"GSD: {res_sensor['gsd']:.2f} cm/px")
    print(f"Scanning Density (Strip): {res_sensor['scanning_density']:.2f} m")
    print(f"Capturing Density (Trigger): {res_sensor['capturing_density']:.2f} m")