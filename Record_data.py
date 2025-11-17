#!/usr/bin/env python3
#-----------------------------------------------------------------------------#
# Record_data.py
#
# A script to record GPS data from a Ublox ZED-F9R to either a .csv or .gpx file.
# The user can choose the format when running the script.
#-----------------------------------------------------------------------------#

import os
import serial
import time
from datetime import datetime
from ublox_gps import UbloxGps
import csv

# Configure your serial port for the ZED-F9R
port = serial.Serial('/dev/ttyTHS1', baudrate=38400, timeout=1)
gps = UbloxGps(port)

def get_basic_gps_data():
    """Fetch basic GPS data (latitude, longitude) from the Ublox GPS module."""
    try:
        geo = gps.geo_coords()
        if geo is not None and geo.lat is not None and geo.lat != 0.0 and geo.lon is not None and geo.lon != 0.0:
            lat = geo.lat
            lon = geo.lon
            ele = getattr(geo, 'height', 0.0) / 1000.0  # height above ellipsoid (convert mm to meters)
            heading = getattr(geo, 'headMot', 0.0)  # heading of motion (degrees)
                        
            return lat, lon, ele, heading
        else:
            print("Waiting for valid fix...")
            return None
    except (ValueError, IOError) as err:
        print("GPS read error:", err)
        return None



def record_to_csv(record_frequency, csv_filename):
    """Record GPS data to a CSV file."""
    print(f"Recording GPS data to {csv_filename}")
    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "Latitude", "Longitude", "Elevation (m)", "Heading (°)"])

        try:
            while True:
                data = get_basic_gps_data()
                if data:
                    lat, lon, ele, heading = data
                    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                    writer.writerow([timestamp, lat, lon, ele, heading])
                    print(f"{timestamp}, Lat: {lat:.8f}, Lon: {lon:.8f}, Ele: {ele:.2f} m, Heading: {heading:.2f}°")
                else:
                    print("Waiting for valid fix...")
                time.sleep(record_frequency)
        except KeyboardInterrupt:
            print("\nStopping CSV recording...")
        finally:
            port.close()
            print(f"Saved CSV file: {csv_filename}")

def record_to_gpx(record_frequency, gpx_filename):
    """Record GPS data to a GPX file."""
    print(f"Recording GPS data to {gpx_filename}")
    with open(gpx_filename, "w") as f:
        write_gpx_header(f)

        try:
            while True:
                data = get_basic_gps_data()
                if data:
                    lat, lon, ele, heading = data
                    write_gpx_point(f, lat, lon, ele, heading)
                    f.flush()
                    print(f"Lat: {lat:.8f}, Lon: {lon:.8f}, Ele: {ele:.2f} m, Heading: {heading:.2f}°")
                else:
                    print("Waiting for valid fix...")
                time.sleep(record_frequency)
        except KeyboardInterrupt:
            print("\nStopping GPX recording...")
        finally:
            write_gpx_footer(f)
            port.close()
            print(f"Saved GPX file: {gpx_filename}")

def write_gpx_header(f):
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<gpx version="1.1" creator="Ublox ZED-F9R Logger" '
            'xmlns="http://www.topografix.com/GPX/1/1">\n')
    f.write('  <trk>\n')
    f.write('    <name>Ublox ZED-F9R Track</name>\n')
    f.write('    <trkseg>\n')

def write_gpx_footer(f):
    f.write('    </trkseg>\n')
    f.write('  </trk>\n')
    f.write('</gpx>\n')

def write_gpx_point(f, lat, lon, ele, heading):
    timestamp_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    f.write(f'      <trkpt lat="{lat:.8f}" lon="{lon:.8f}">\n')
    f.write(f'        <ele>{ele:.2f}</ele>\n')
    f.write(f'        <course>{heading:.2f}</course>\n')
    f.write(f'        <time>{timestamp_str}</time>\n')
    f.write('      </trkpt>\n')

if __name__ == '__main__':
    record_frequency = float(input("Enter the record frequency in seconds (e.g., 1 for 1 second): "))
    choice = input("Choose recording format (csv/gpx): ").strip().lower()

    # Create "results" directory if it doesn't exist
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)

    # Name output file with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    if choice == 'csv':
        csv_filename = os.path.join(results_dir, f"gps_log_{timestamp}.csv")
        record_to_csv(record_frequency, csv_filename)
    elif choice == 'gpx':
        gpx_filename = os.path.join(results_dir, f"gps_log_{timestamp}.gpx")
        record_to_gpx(record_frequency, gpx_filename)
    else:
        print("Invalid choice. Please choose either 'csv' or 'gpx'.")