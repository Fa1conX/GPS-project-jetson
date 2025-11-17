import serial
import time
import os
from pathlib import Path

def get_gps_coordinates():
    """Prompt the user to input GPS coordinates."""
    try:
        latitude = float(input("Enter latitude: "))
        longitude = float(input("Enter longitude: "))
        return latitude, longitude
    except ValueError:
        print("Invalid input. Please enter numeric values.")
        return get_gps_coordinates()

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
    command = f"<THR:{throttle};STR:{steering}>"
    serial_conn.write(command.encode('utf-8'))

def main():
    # Default tuning parameters
    default_speed = 100  # Throttle value (-255 to 255)
    default_steering = 90  # Steering angle (0 to 180)

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
        latitude, longitude = get_gps_coordinates()
        print(f"Navigating to: Latitude {latitude}, Longitude {longitude}")
        send_command(serial_conn, default_speed, default_steering)

    elif mode == '2':
        coordinates = read_gpx_file()
        print("Navigating through the following coordinates:")
        for lat, lon in coordinates:
            print(f"Latitude: {lat}, Longitude: {lon}")
            send_command(serial_conn, default_speed, default_steering)
            time.sleep(2)  # Simulate navigation delay

    else:
        print("Invalid mode selected.")

    serial_conn.close()

if __name__ == "__main__":
    main()