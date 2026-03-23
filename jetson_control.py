import serial
import time
import math
import os
from pathlib import Path
import math
from ublox_gps import UbloxGps
import threading
import traceback

#============================================================================
# JETSON GPS AUTONOMOUS NAVIGATION SYSTEM
#============================================================================
# Configuration: Which heading source to use when navigating waypoints
# Options:
#   "zed_f9r"         - ZED-F9R GPS/IMU (NAV-ATT message, recommended)
#   "arduino_bno055"  - Arduino BNO055 IMU (via serial, requires calibration)
#
# The heading source is selected interactively at startup. Position data
# always comes from ZED-F9R. Alignment status (ESF-ALG) is optional.
#
# Thread-safe GPS state dict: Updated by background gps_reader_thread(),
# read by navigate_to_waypoint() on main thread via gps_lock.
#============================================================================

# Configuration: Which heading source to use
# Will be set by main() based on user selection
HEADING_SOURCE = None

gps_state = {
    "lat": None,
    "lon": None,
    "ele": None,
    "heading": None,
    "aligned": False,
    "heading_source": None,  # "zed_f9r" or "arduino_bno055"
    "last_update": 0.0
}

gps_lock = threading.Lock()

#Serial port for the Ublox GPS
port = serial.Serial('/dev/ttyTHS1', baudrate=38400, timeout=0.2)
gps = UbloxGps(port)

# Serial port for Arduino (will be opened in main)
arduino_serial = None

def gps_reader_thread(gps):
    while True:
        try:
            geo = gps.geo_coords()
            # Alignment status check (required for safe navigation)
            alg = None
            try:
                alg = gps.imu_alignment()
            except (ValueError, IOError) as e:
                # IMU alignment not available; carry on with position-only mode
                pass

            # Read heading based on configured source
            att = None
            if HEADING_SOURCE == "zed_f9r":
                try:
                    att = gps.veh_attitude()
                except (ValueError, IOError) as e:
                    # Heading not available this cycle; carry on
                    pass

            with gps_lock:
                if geo and geo.lat not in (None, 0.0) and geo.lon not in (None, 0.0):
                    gps_state["lat"] = geo.lat
                    gps_state["lon"] = geo.lon
                    gps_state["ele"] = getattr(geo, "height", 0.0) / 1000.0
                    gps_state["last_update"] = time.time()

                # Update heading based on configured source
                if HEADING_SOURCE == "zed_f9r" and att and getattr(att, "heading", None) is not None:
                    gps_state["heading"] = att.heading
                    gps_state["heading_source"] = "zed_f9r"
                elif HEADING_SOURCE == "arduino_bno055" and arduino_serial:
                    # Try to read heading from Arduino (non-blocking)
                    heading = read_heading_arduino(arduino_serial)
                    if heading is not None:
                        gps_state["heading"] = heading
                        gps_state["heading_source"] = "arduino_bno055"

                # Set alignment status if available (alg.flags.status == 3 means aligned)
                if alg and hasattr(alg, 'flags') and hasattr(alg.flags, 'status'):
                    gps_state["aligned"] = (alg.flags.status == 3)
                else:
                    gps_state["aligned"] = False

        except Exception as e:
            print("GPS thread error:")
            traceback.print_exc()
        
        time.sleep(0.05)


def read_heading_arduino(arduino_port, timeout=0.5):
    """
    Non-blocking attempt to read heading from Arduino BNO055.
    Looks for <HEAD:xxx> format in serial buffer.
    Returns heading value (0-360) or None if not available.
    This function doesn't block; it just checks what's available.
    """
    if not arduino_port:
        return None
    
    try:
        # Read available data without blocking
        if arduino_port.in_waiting > 0:
            line = arduino_port.readline().decode('utf-8', errors='ignore').strip()
            if line.startswith("<HEAD:") and line.endswith(">"):
                heading_str = line[len("<HEAD:"):-1]
                try:
                    heading = float(heading_str)
                    if 0 <= heading < 360:
                        return heading
                except ValueError:
                    pass
    except Exception as e:
        pass
    
    return None


def input_gps_coordinates():
    """
    Prompt the user to input GPS coordinates.
    """
    try:
        latitude = float(input("Enter latitude: "))
        longitude = float(input("Enter longitude: "))
        return latitude, longitude
    except ValueError:
        print("Invalid input. Please enter numeric values.")
        return input_gps_coordinates()

def read_gpx_file():
    """
    Prompt the user to specify a GPX file and read coordinates.
    """
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
    """Navigate to a given waypoint using GPS/heading data.
    
    Continuously reads GPS position and heading from gps_state dict (populated
    by background gps_reader_thread), calculates bearing and distance to waypoint,
    and sends steering/throttle commands to Arduino at 10 Hz until waypoint reached.
    
    Args:
        serial_conn: Arduino serial connection for sending motor/steering commands
        waypoint_lat: Target latitude in degrees
        waypoint_lon: Target longitude in degrees
        off_path_threshold: Distance in meters (reserved for future path correction)
    
    Stops when distance < 1.0 meter or GPS/heading unavailable for 5+ seconds.
    """

    print(f"Navigating to waypoint: Latitude {waypoint_lat}, Longitude {waypoint_lon}")
    print(f"Heading source: {HEADING_SOURCE}")
    
    ready_wait_count = 0
    max_ready_wait = 100  # ~5 seconds at 0.1s per iteration before timing out

    #last_recalculation_time = time.time()
    while True:
        with gps_lock:
            current_lat = gps_state["lat"]
            current_lon = gps_state["lon"]
            elevation = gps_state["ele"]
            current_heading = gps_state["heading"]
            align = gps_state["aligned"]
            heading_source = gps_state["heading_source"]

        # Check if we have minimum required data for navigation
        if current_lat is not None and current_heading is not None:
            with gps_lock:
                age = time.time() - gps_state["last_update"]

            if age > 1.0:
                print("WARNING: GPS data stale (age {:.1f}s)".format(age))
                time.sleep(0.1)
                continue

            # Log alignment status if available
            if not align:
                print("Note: IMU alignment status is FALSE (heading may drift over time)")

            # Calculate distance and bearing to waypoint
            distance_to_waypoint = calculate_distance(current_lat, current_lon, waypoint_lat, waypoint_lon)
            bearing_to_waypoint = calculate_bearing(current_lat, current_lon, waypoint_lat, waypoint_lon)

            print(f"Distance: {distance_to_waypoint:.2f}m, Bearing: {bearing_to_waypoint:.1f}°, Heading: {current_heading:.1f}°")

            # Send commands to Arduino
            if distance_to_waypoint < 30.0:
                throttle = 50  # Slow down when close
            elif distance_to_waypoint < 5.0:
                throttle = 30  # Further slow down when very close
            else:
                throttle = 60  # Normal speed
            
            relative_angle = calculate_relative_angle(current_heading, bearing_to_waypoint)
            steering = int(map_angle_to_steering(relative_angle, max_steering=45))
            
            steer_mag = abs(steering - 90)  # Distance from neutral (90)

            if steer_mag < 10:
                throttle *= 1.0
            elif steer_mag < 20:
                throttle *= 0.7
            elif steer_mag < 30:
                throttle *= 0.5
            else:
                throttle *= 0.3

            # Clamp throttle to valid range
            throttle = int(max(-255, min(255, throttle)))
            
            send_command(serial_conn, throttle, steering)
            
            # Stop navigation if close to waypoint
            if distance_to_waypoint < 1.0:
                print("Reached waypoint!")
                send_command(serial_conn, 0, 90)  # Stop vehicle
                break            
        else:
            # Still waiting for GPS/heading to be ready
            ready_wait_count += 1
            if ready_wait_count % 10 == 0:  # Print every 1 second
                print(f"Waiting for GPS/heading ready... (lat: {current_lat}, heading: {current_heading}, aligned: {align})")
            
            if ready_wait_count > max_ready_wait:
                print("ERROR: GPS or heading not available after timeout. Check connection and heading source configuration.")
                send_command(serial_conn, 0, 90)  # Stop vehicle before exiting
                break

        time.sleep(0.1)  # 10 Hz polling rate



def main():
    global HEADING_SOURCE, arduino_serial
    
    # Serial communication setup Arduino
    serial_port = '/dev/ttyUSB0'
    baud_rate = 115200

    try:
        serial_conn = serial.Serial(serial_port, baud_rate, timeout=0.2)
        print(f"Connected to Arduino on {serial_port} at {baud_rate} baud.")
    except serial.SerialException as e:
        print(f"Failed to connect to Arduino: {e}")
        return
    
    # Store Arduino connection globally for GPS thread access
    arduino_serial = serial_conn
    
    #-----

    gps_thread = threading.Thread(
        target=gps_reader_thread,
        args=(gps,),
        daemon=True
    )
    gps_thread.start()

    print("GPS reader thread started.")

    # Select heading source
    print("\nSelect heading source:")
    print("1. ZED-F9R GPS/IMU (recommended)")
    print("2. Arduino BNO055 IMU (requires BNO055 calibration)")
    heading_choice = input("Enter heading source (1 or 2): ")
    
    if heading_choice == '1':
        HEADING_SOURCE = "zed_f9r"
        print("Using ZED-F9R heading source.")
    elif heading_choice == '2':
        HEADING_SOURCE = "arduino_bno055"
        print("Using Arduino BNO055 heading source.")
        print("IMPORTANT: Ensure the vehicle is facing true north when BNO055 powers on!")
    else:
        print("Invalid heading source selection. Defaulting to ZED-F9R.")
        HEADING_SOURCE = "zed_f9r"

    print("Select mode:")
    print("1. Input GPS coordinates manually")
    print("2. Read coordinates from GPX file")
    mode = input("Enter mode (1 or 2): ")

    if mode == '1':
        #latitude, longitude = input_gps_coordinates()
        latitude, longitude = 32.770729, -117.188756 #for testing, 
        #coordinates hardcoded for spot in middle of road behind BEC
        print(f"Navigating to Latitude {latitude}, Longitude {longitude}")
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