"""
Test script for testing ability of jetson to control vehicle movement.
"""

import serial
import time
import jetson_control

port = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=1)

jetson_control.send_command(serial_conn=port, throttle=15, steering=50)
time.sleep(3)
jetson_control.send_command(serial_conn=port, throttle=-10, steering=100)
jetson_control.send_command(serial_conn=port, throttle=0, steering=90)
