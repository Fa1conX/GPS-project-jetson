#!/usr/bin/env python3
#-----------------------------------------------------------------------------
# record_gps_to_gpx_full.py
#
# Records GPS data from a Ublox ZED-F9R to a .gpx file
# using the SparkFun ublox_gps Python library.
#
# Logs latitude, longitude, elevation, and heading.
#-----------------------------------------------------------------------------

import os
import serial
import time
from datetime import datetime
from ublox_gps import UbloxGps

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
    

# Name output GPX file with timestamp
timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
gpx_filename = os.path.join(results_dir, f"gps_log_{timestamp}.gpx")

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

def run_gpx(record_frequency=record_frequency):
    print(f"Recording GPS data to {gpx_filename}")
    with open(gpx_filename, "w") as f:
        write_gpx_header(f)

        try:
            print("Listening for UBX messages...")
            while True:
                try:
                    geo = gps.geo_coords()
                    if geo is not None and geo.lat is not None and geo.lon is not None:
                        # Use PVT fields: lat, lon, height (mm), headMot (deg * 1e-5)
                        lat = geo.lat
                        lon = geo.lon
                        ele = getattr(geo, 'height', 0.0)  # height above ellipsoid (meters)
                        heading = getattr(geo, 'headMot', 0.0)  # heading of motion (degrees)
                        
                        print(f"Lat: {lat:.8f}, Lon: {lon:.8f}, Ele: {ele:.2f} m, Heading: {heading:.2f}°")

                        write_gpx_point(f, lat, lon, ele, heading)
                        f.flush()
                    else:
                        print("Waiting for valid fix...")
                    time.sleep(record_frequency)
                except (ValueError, IOError) as err:
                    print("GPS read error:", err)
                    time.sleep(record_frequency)

        except KeyboardInterrupt:
            print("\nStopping recording...")

        finally:
            write_gpx_footer(f)
            port.close()
            print(f"Saved GPX file: {gpx_filename}")

if __name__ == '__main__':
    run_gpx()
