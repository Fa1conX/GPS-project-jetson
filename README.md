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

3. Set udev rules for persistent permissions:
   ```bash
   sudo nano /etc/udev/rules.d/99-uart-permissions.rules
   # Add: KERNEL=="ttyTHS1", MODE="0666"
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```
   (restart)

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
The script will prompt you for:
1. **Heading source selection**:
   - `1`: ZED-F9R GPS/IMU (recommended, auto-calibrating to true north)
   - `2`: Arduino BNO055 IMU (requires BNO055 calibration; vehicle must face true north at power-on)

2. **Navigation mode**:
   - `1`: Input GPS coordinates manually
   - `2`: Load waypoints from `.gpx` track file (multi-waypoint support)

During navigation, the system:
- Waits for GPS position fix and heading data (timeout: 5 seconds)
- Logs alignment status each iteration (indicates if IMU heading is initialized)
- Navigates at 10 Hz command rate, printing real-time:
  - Distance to waypoint (meters)
  - Target bearing (degrees)
  - Current heading (degrees)
  - Warnings if GPS data is stale (> 1 second old)
- Stops when within 1.0 meter of waypoint
- Returns to RC control if joystick moves from neutral

**Note**: Testing uses hardcoded coordinates (32.770729, -117.188756) on line 371.

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
├── examples/                   # SparkFun GPS library examples
├── csv_record.py               # (Deprecated: use Record_data.py)
├── gpx_record.py               # (Deprecated: use Record_data.py)
└── RCconverter/                # RC PWM converter utilities
```

## Key Features

**Jetson (Python)**
- Dual heading source support: ZED-F9R GPS/IMU (recommended) or Arduino BNO055 IMU (selectable at runtime)
- Thread-safe GPS state dictionary with lock-based synchronization
- Real-time Distance/Bearing/Heading output during navigation
- Adaptive throttle based on steering angle (reduces speed on tight turns)
- Flat-earth distance/bearing calculations (~111 km accuracy range)
- Binary serial protocol for motor/steering commands
- IMU alignment status logging (indicates heading calibration state)
- GPS stale data detection (warns if position data older than 1 second)
- Graceful timeout if GPS/heading unavailable for 5+ seconds

**Arduino (C++)**
- Nonblocking binary packet parser for Jetson commands
- RC PWM input capture and mode arbitration
- 2-second neutral hold before switching to Jetson mode
- Deadband filtering for motor/servo to reduce chatter
- Real-time debug output with mode, speed, direction, and RC/Jetson signal status
- BNO055 IMU support integrated for heading backup

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

### Steering Calculation Details

The steering algorithm converts heading/bearing to servo commands:
1. Calculate relative angle between current heading and target bearing: [-180°, +180°]
   - Negative = turn left, Positive = turn right
2. Clamp relative angle to max steering range (±45°) for vehicle capability
3. Convert from relative (-45 to +45) to absolute servo position (45 to 135, where 90 = neutral)
4. Apply distance-based throttle reduction:
   - > 30m: 30% max throttle
   - 5–30m: 20% max throttle  
   - < 5m: 15% max throttle
5. Apply adaptive steering-based throttle multiplier:
   - Straight (< 10°): 100% of distance throttle
   - Moderate turn (10-20°): 70%
   - Sharp turn (20-30°): 50%
   - Very sharp (> 30°): 30%
   - This prevents flipping/stalling on sharp turns

### Debug Scripts
- `read_arduino_status.py`: Monitor Arduino mode, speed, steering, and signal status in real-time
- `examples/geo_coords_ex1.py`: Verify GPS position fix independently

## Known Limitations & TODOs

- **u-center GPS config** not yet documented
- **Path smoothing** not implemented (point-to-point navigation only)
- **Obstacle avoidance** not supported
- **BNO055 IMU** support integrated (selectable at startup alongside ZED-F9R)
- **ROS2 migration** planned for future version
- **Flat-earth approximation** valid for areas < 100 km

## References

- [SparkFun Ublox GPS Python Library](https://github.com/sparkfun/Qwiic_Ublox_Gps_Py)
- [ZED-F9R Hookup Guide](https://learn.sparkfun.com/tutorials/sparkfun-gps-rtk-dead-reckoning-zed-f9r-hookup-guide/)

---

*TODO:*
- Document GPS configuration workflow in u-center
- ROS2 node implementation
- Path planning and obstacle avoidance algorithms
