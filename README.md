# GPS-Project-Jetson: Autonomous Vehicle Navigation System

An autonomous vehicle navigation system combining a **Jetson Nano**, **Arduino Nano**, and **Ublox ZED-F9R** GPS/IMU module for GPS-waypoint navigation with RC manual override capability.

## Overview

This project enables autonomous navigation to GPS waypoints while maintaining manual RC control override. The system:
- Reads real-time GPS coordinates and heading from a ZED-F9R module
- Calculates bearing and distance to target waypoints
- Commands motor throttle and steering servo via binary serial protocol
- Arbitrates between RC manual control and Jetson autonomous commands
- Logs GPS tracks to CSV/GPX format

## Hardware

| Component | Model | Connection |
|-----------|-------|-----------|
| **SBC** | NVIDIA Jetson Nano | - |
| **Microcontroller** | Arduino Nano | `/dev/ttyUSB0` @ 115200 baud |
| **GPS/IMU** | Ublox ZED-F9R | `/dev/ttyTHS1` @ 38400 baud (GPIO pins 8/10) |
| **Motor Driver** | Motor driver module | PWM + direction pins (Arduino 5/4) |
| **Servo** | Steering servo | PWM output (Arduino pin 6) |
| **RC Receiver** | PWM receiver | RC throttle/steering inputs (Arduino pins 2/3) |

## Quick Start

### Prerequisites
```bash
pip install pyserial
```

### Jetson Setup (One-Time)
1. Disable serial-getty service for ZED-F9R access:
   ```bash
   sudo systemctl stop nvgetty serial-getty@ttyTHS1.service
   sudo systemctl disable nvgetty serial-getty@ttyTHS1.service
   ```

2. Add user to dialout group:
   ```bash
   sudo usermod -aG dialout $USER
   newgrp dialout  # Apply immediately
   ```

3. (Optional) Set udev rules for persistent permissions:
   ```bash
   sudo nano /etc/udev/rules.d/99-uart-permissions.rules
   # Add: KERNEL=="ttyTHS1", MODE="0666"
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```

4. Verify GPIO UART works:
   ```bash
   python3 -c "import serial; s = serial.Serial('/dev/ttyTHS1', 38400); print('✓ GPS connected')"
   ```

### Arduino Setup
- Compile and flash `RCandJetsoncontrol/RCandJetsoncontrol.ino` to Arduino Nano
- Connect:
  - RC Throttle → Pin 2
  - RC Steering → Pin 3
  - Motor direction → Pin 4, Motor PWM → Pin 5
  - Servo signal → Pin 6
  - Jetson serial → Pins RX/TX @ 115200 baud

### Run Autonomous Navigation
```bash
python3 jetson_control.py
```
Options:
1. **Manual waypoint**: Enter GPS coordinates manually
2. **GPX file**: Load waypoints from `.gpx` track file (multi-waypoint support)

The system will:
- Wait for GPS/heading alignment (NAV-ATT accuracy < 5°)
- Navigate to each waypoint at 10 Hz command rate
- Stop when within 1.0 meter of waypoint
- Switch to RC control if joystick moves from neutral

### Record GPS Tracks
```bash
python3 Record_data.py
```
Outputs to `results/gps_log_*.{csv,gpx}` with timestamps, position, elevation, and heading.

## Project Structure

```
.
├── jetson_control.py           # Main Jetson navigation script
├── RCandJetsoncontrol/
│   └── RCandJetsoncontrol.ino  # Arduino motor/servo/RC arbitration logic
├── Record_data.py              # GPS track recorder (CSV/GPX)
├── read_arduino_status.py      # Debug helper to read Arduino serial output
├── ublox_gps/                  # Modified SparkFun Ublox Python library
├── results/                    # Output directory for GPS logs
├── setupnotes.txt              # Hardware setup reference
└── examples/                   # SparkFun GPS library examples
```

## Key Features

**Jetson (Python)**
- Thread-safe GPS state dictionary with lock-based synchronization
- Flat-earth distance/bearing calculations (~111 km accuracy range)
- Adaptive throttle based on steering angle (reduces speed on tight turns)
- Binary serial protocol for motor/steering commands

**Arduino (C++)**
- Nonblocking binary packet parser for Jetson commands
- RC PWM input capture and mode arbitration
- 2-second neutral hold before switching to Jetson mode
- Deadband filtering for motor/servo to reduce chatter
- Real-time debug output with mode, speed, direction, and RC/Jetson signal status

## Control Mode Arbitration

| Condition | Mode | Priority |
|-----------|------|----------|
| RC joystick moved from neutral | RC Manual | **High** |
| RC neutral for 2+ seconds | Jetson Autonomous | Medium |
| No Jetson command for 500ms | Failsafe (stop) | Low |

## Serial Protocols

**Jetson → Arduino (Binary, 115200 baud)**
```
[0xAA] [throttle: -255..255] [steering: 0..180] [reserved] [checksum] [0x55]
```
Checksum: `(throttle + steering + reserved) & 0xFF`

**Arduino debug output (serial monitor)**
```
<MODE:RC;SPD:128;DIR:FWD;STR:90;RCOK:1;JETOK:1;thrPulse;1495>
```

**GPS → Jetson (Ublox UBX protocol, 38400 baud)**
- NAV-PVT: Position, velocity, time
- NAV-ATT: Heading, attitude, heading accuracy
- ESF-ALG: IMU alignment status

## Development & Debugging

### Common Issues

| Issue | Solution |
|-------|----------|
| GPS reports "not aligned" | Ensure 5+ meter sky visibility, heading accuracy typically < 3° outdoors |
| Steering servo jitters | Increase `SERVO_DEADBAND` in Arduino code |
| Motor buzzes at low speeds | Increase `MOTOR_DEADBAND` (default: 5 PWM) |
| RC override not triggering | Verify PWM pulses on pins 2/3 reach 1400–1600 µs range |
| Serial permission denied | Run `sudo chmod 666 /dev/ttyTHS1` or apply udev rules |

### Debug Scripts
- `read_arduino_status.py`: Monitor Arduino mode, speed, steering, and signal status in real-time
- `examples/geo_coords_ex1.py`: Verify GPS position fix independently

## Known Limitations & TODOs

- ⚠️ **u-center GPS config** not yet documented
- ⚠️ **Path smoothing** not implemented (point-to-point navigation only)
- ⚠️ **Obstacle avoidance** not supported
- ⚠️ **BNO055 IMU** code included but not integrated (ZED-F9R heading is sufficient)
- 🔄 **ROS2 migration** planned for future version
- 📐 **Flat-earth approximation** valid for areas < 100 km

## References

- [SparkFun Ublox GPS Python Library](https://github.com/sparkfun/Qwiic_Ublox_Gps_Py)
- [ZED-F9R Hookup Guide](https://learn.sparkfun.com/tutorials/sparkfun-gps-rtk-dead-reckoning-zed-f9r-hookup-guide/)

---

*TODO:*
- Document GPS configuration workflow in u-center
- ROS2 node implementation
- Path planning and obstacle avoidance algorithms
