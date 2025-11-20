"""
Test script for testing ability of jetson to control vehicle movement.
"""

import serial
import time
import jetson_control

port = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=1)

jetson_control.send_command(serial_conn=port, throttle=10, steering=90)  # Example command to move forward
time.sleep(1)
jetson_control.send_command(serial_conn=port, throttle=-10, steering=-80)  # Stop the vehicle