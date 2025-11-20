"""
Test script for testing ability of jetson to control vehicle movement.
"""

import serial
import time
import jetson_control

port = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=1)

jetson_control.send_command(serial_conn=port, throttle=40, steering=0)
time.sleep(2)
jetson_control.send_command(serial_conn=port, throttle=-10, steering=100)