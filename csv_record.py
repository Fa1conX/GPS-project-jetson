import os
import serial
import time
import csv
from datetime import datetime
from ublox_gps import UbloxGps

print("temporarily depricated, use Record_data.py instead")
"""

# Configure your serial port for the ZED-F9R
port = serial.Serial('/dev/ttyTHS1', baudrate=38400, timeout=1)
gps = UbloxGps(port)

# Prompt user for record frequency
if __name__ == '__main__':
    record_frequency = float(input("Enter the record frequency in seconds (e.g., 1 for 1 second): "))
else:
    record_frequency = 0.25  # default to 0.25 seconds if not run as main

# Create "results" directory if it doesn't exist
results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(results_dir, exist_ok=True)

# Name output CSV file with timestamp
timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
csv_filename = os.path.join(results_dir, f"gps_log_{timestamp}.csv")

def run_csv(record_frequency=record_frequency):
    print(f"Recording GPS data to {csv_filename}")
    with open(csv_filename, "w", newline="") as csvfile:
        csv_writer = csv.writer(csvfile)
        # Write CSV header
        csv_writer.writerow(["Timestamp", "Latitude", "Longitude", "Elevation (m)", "Heading (°)"])

        try:
            print("Listening for UBX messages...")
            while True:
                try:
                    geo = gps.geo_coords()
                    if geo is not None and geo.lat is not None and geo.lon is not None:
                        # Use PVT fields: lat, lon, height (mm), headMot (deg * 1e-5)
                        lat = geo.lat
                        lon = geo.lon
                        ele = getattr(geo, 'height', 0.0) / 1000.0  # height above ellipsoid (convert mm to meters)
                        heading = getattr(geo, 'headMot', 0.0)  # heading of motion (degrees)
                        timestamp_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

                        print(f"Timestamp: {timestamp_str}, Lat: {lat:.8f}, Lon: {lon:.8f}, Ele: {ele:.2f} m, Heading: {heading:.2f}°")

                        # Write data to CSV
                        csv_writer.writerow([timestamp_str, lat, lon, ele, heading])
                        csvfile.flush()
                    else:
                        print("Waiting for valid fix...")
                    time.sleep(record_frequency)
                except (ValueError, IOError) as err:
                    print("GPS read error:", err)
                    time.sleep(record_frequency)

        except KeyboardInterrupt:
            print("\nStopping recording...")

        finally:
            port.close()
            print(f"Saved CSV file: {csv_filename}")

if __name__ == '__main__':
    run_csv()
"""