import serial
import time
import os
from pathlib import Path
import math
from Record_data import get_basic_gps_data

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
    """Send throttle and steering commands to the Arduino."""
    command = f"<THR:{int(throttle)};STR:{int(steering)}>\n"
    serial_conn.write(command.encode('utf-8'))

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate the bearing between two GPS coordinates."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.atan2(x, y)
    return math.degrees(bearing) % 360

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate the distance between two GPS coordinates using the haversine formula."""
    R = 6371e3  # Earth radius in meters
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def navigate_to_waypoint(serial_conn, waypoint_lat, waypoint_lon, off_path_threshold=5.0):
    """Navigate to a given waypoint using GPS data."""
    print(f"Navigating to waypoint: Latitude {waypoint_lat}, Longitude {waypoint_lon}")

    last_recalculation_time = time.time()
    while True:
        # Poll GPS data at 10 Hz
        gps_data = get_basic_gps_data()
        if gps_data:
            current_lat, current_lon, _, _ = gps_data

            # Calculate distance and bearing to waypoint
            distance_to_waypoint = calculate_distance(current_lat, current_lon, waypoint_lat, waypoint_lon)
            bearing_to_waypoint = calculate_bearing(current_lat, current_lon, waypoint_lat, waypoint_lon)

            print(f"Distance to waypoint: {distance_to_waypoint:.2f} m, Bearing: {bearing_to_waypoint:.2f}°")

            # Send commands to Arduino
            throttle = 100  # Example throttle value
            steering = int(bearing_to_waypoint)  # Map bearing to steering angle
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