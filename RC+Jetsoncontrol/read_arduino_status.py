import serial
import os

ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)

while True:
    line = ser.readline().decode().strip()
    if line:
        print("Arduino:", line)
        # Prompt user if they want to write debug to a file
        write_to_file = input("Do you want to write debug output to a file? (yes/no): ").strip().lower()

        if write_to_file == 'yes':
            # Ensure the results directory exists
            results_dir = os.path.join(os.path.dirname(__file__), 'results')
            os.makedirs(results_dir, exist_ok=True)
            
            # Create a file to write debug output
            debug_file_path = os.path.join(results_dir, 'arduino_debug.log')
            with open(debug_file_path, 'w') as debug_file:
                print(f"Debug output will be written to: {debug_file_path}")
                
                while True:
                    line = ser.readline().decode().strip()
                    if line:
                        print("Arduino:", line)
                        debug_file.write(line + '\n')
                        debug_file.flush()
        else:
            while True:
                line = ser.readline().decode().strip()
                if line:
                    print("Arduino:", line)
# Expected Arduino debug output format:
# MODE	"RC" = manual RC override active, "JETSON" = autonomous control
# SPD	Current PWM output (0–255)
# DIR	"FWD" or "REV" (based on direction pin)
# STR	Steering servo angle (0–180)
# RCOK	1 if valid RC signal detected
# JETOK	1 if valid Jetson command received recently