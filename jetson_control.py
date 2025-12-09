import serial
import time
import math
import os
from pathlib import Path
import math
from Record_data import get_basic_gps_data
from ublox_gps import UbloxGps

port = serial.Serial('/dev/ttyTHS1', baudrate=38400, timeout=1)
gps = UbloxGps(port)


def input_gps_coordinates():
    """Prompt the user to input GPS coordinates."""
    try:
        latitude = float(input("Enter latitude: "))
        longitude = float(input("Enter longitude: "))
        return latitude, longitude
    except ValueError:
        print("Invalid input. Please enter numeric values.")
        return input_gps_coordinates()

def read_gpx_file():
    """Prompt the user to specify a GPX file and read coordinates."""
    file_path = input("Enter the path to the GPX file: ")
    if not Path(file_path).is_file():
        print("File not found. Please try again.")
        return read_gpx_file()

    coordinates = []
    with open(file_path, 'r') as file:
        for line in file:
            if '<trkpt' in line:
                parts = line.split('"')
                lat = float(parts[1])
                lon = float(parts[3])
                coordinates.append((lat, lon))
    return coordinates

def send_command(serial_conn, throttle, steering):
    """
    Send binary throttle/steering packet to Arduino.
    throttle: -255 to 255 (int)
    steering: 0 to 180 (int)
    """
    t = int(throttle)
    s = int(steering)

    # Clamp values
    t = max(-255, min(255, t))
    s = max(0, min(180, s))

    # Convert throttle to signed int8 format
    if t < 0:
        t = 256 + t   # convert negative int8 to unsigned byte

    reserved = 0
    checksum = (t + s + reserved) & 0xFF

    packet = bytes([
        0xAA,       # start byte
        t & 0xFF,   # throttle
        s & 0xFF,   # steering
        reserved,   # reserved for future
        checksum,   # checksum
        0x55        # end byte
    ])

    serial_conn.write(packet)


def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate the bearing between two GPS coordinates."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.atan2(x, y)
    return math.degrees(bearing) % 360
#--- new stuff 
def get_gps_data_for_steering():
    """
    Fetch GPS data from Ublox ZED-F9R for steering purposes.
    Returns:
        lat (float): Latitude in degrees
        lon (float): Longitude in degrees
        ele (float): Elevation in meters
        heading (float): Heading of motion in degrees (0-360)
    """
    try:
        geo = gps.geo_coords()
        if geo is not None and geo.lat not in (None, 0.0) and geo.lon not in (None, 0.0):
            lat = geo.lat
            lon = geo.lon
            ele = getattr(geo, 'height', 0.0) / 1000.0  # mm → meters
            heading = getattr(geo, 'headMot', 0.0)     # degrees, 0-360

            return lat, lon, ele, heading
        else:
            print("Waiting for valid GPS fix...")
            return None
    except (ValueError, IOError) as err:
        print("GPS read error:", err)
        return None

def calculate_relative_angle(current_heading, target_bearing):
    """
    Compute the relative angle between the current heading and the target bearing.
    Returns an angle in degrees (-180 to 180):
        negative = turn left
        positive = turn right
    """
    angle = target_bearing - current_heading
    # Normalize to [-180, 180]
    if angle > 180:
        angle -= 360
    elif angle < -180:
        angle += 360
    return angle


def map_angle_to_steering(relative_angle, max_steering=45):
    """
    Convert relative angle (-180 to 180) to a steering value for Arduino.
    max_steering is the maximum steering angle in degrees your servo can take.
    """
    # Clamp relative angle to max_steering
    if relative_angle > max_steering:
        return max_steering
    elif relative_angle < -max_steering:
        return -max_steering
    else:
        return relative_angle


# end new stuff

def calculate_distance(lat1, lon1, lat2, lon2):
    """Approximate distance between two GPS coords using simple trig (flat-earth approximation)."""
    # Convert degrees → radians
    lat1_r = math.radians(lat1)
    
    # Scale factors (approx):
    meters_per_deg_lat = 111_320                 # constant
    meters_per_deg_lon = 111_320 * math.cos(lat1_r)  # shrinks with latitude

    # Differences
    dlat = (lat2 - lat1) * meters_per_deg_lat
    dlon = (lon2 - lon1) * meters_per_deg_lon

    # Pythagorean distance
    return math.sqrt(dlat*dlat + dlon*dlon)

def navigate_to_waypoint(serial_conn, waypoint_lat, waypoint_lon, off_path_threshold=5.0):
    """Navigate to a given waypoint using GPS data.
        distance in meters

    """

    print(f"Navigating to waypoint: Latitude {waypoint_lat}, Longitude {waypoint_lon}")

    last_recalculation_time = time.time()
    while True:
        # Poll GPS data at 10 Hz
        gps_data = get_basic_gps_data()
        if gps_data:
            current_lat, current_lon, _, current_heading = get_gps_data_for_steering()

            # Calculate distance and bearing to waypoint
            distance_to_waypoint = calculate_distance(current_lat, current_lon, waypoint_lat, waypoint_lon)
            bearing_to_waypoint = calculate_bearing(current_lat, current_lon, waypoint_lat, waypoint_lon)

            print(f"Distance to waypoint: {distance_to_waypoint:.2f} m, Bearing: {bearing_to_waypoint:.2f}°")

            # Send commands to Arduino
            throttle = 40  # Example throttle value
            _, _, _, current_heading = get_gps_data_for_steering()
            relative_angle = calculate_relative_angle(current_heading, bearing_to_waypoint)
            steering = int(map_angle_to_steering(relative_angle, max_steering=45))


            send_command(serial_conn, throttle, steering)

            # Recalculate route every second if off-path
            current_time = time.time()
            if current_time - last_recalculation_time >= 1.0:
                last_recalculation_time = current_time
                if distance_to_waypoint > off_path_threshold:
                    print("Recalculating route...")

            # Stop navigation if close to waypoint
            if distance_to_waypoint < 1.0:
                print("Reached waypoint!")
                send_command(serial_conn, 0, 90)  # Stop vehicle
                break

        time.sleep(0.1)  # 10 Hz polling rate



def main():
    # Serial communication setup
    serial_port = '/dev/ttyUSB0'  # Adjust based on your setup
    baud_rate = 115200

    try:
        serial_conn = serial.Serial(serial_port, baud_rate, timeout=1)
        print(f"Connected to Arduino on {serial_port} at {baud_rate} baud.")
    except serial.SerialException as e:
        print(f"Failed to connect to Arduino: {e}")
        return

    print("Select mode:")
    print("1. Input GPS coordinates manually")
    print("2. Read coordinates from GPX file")
    mode = input("Enter mode (1 or 2): ")

    if mode == '1':
        latitude, longitude = input_gps_coordinates()
        navigate_to_waypoint(serial_conn, latitude, longitude)

    elif mode == '2':
        coordinates = read_gpx_file()
        print("Navigating through the following waypoints:")
        for i, (lat, lon) in enumerate(coordinates):
            print(f"Waypoint {i + 1}: Latitude {lat}, Longitude {lon}")
            navigate_to_waypoint(serial_conn, lat, lon)
        print("Finished navigating all waypoints.")

    else:
        print("Invalid mode selected")

    serial_conn.close()

if __name__ == "__main__":
    main()