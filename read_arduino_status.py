import serial
import os



def read_arduino_status(save_to_file):
    try:
        ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=1)
    except serial.SerialException as e:
        print(f"Error: Could not open serial port '/dev/ttyUSB0'. Ensure the device is connected and the port is correct.")
        print(f"Details: {e}")
        return

    if save_to_file:
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
            line = ser.readline()
            if line:
                print("Arduino:", line.strip())


# Prompt user for record frequency
if __name__ == '__main__':
    save_to_file = input("Save debug output to file? (Y/N): ").strip().lower() == 'y'
    read_arduino_status(save_to_file)
else:
    save_to_file = False  # default to False if not run as main
    read_arduino_status(save_to_file)

# Expected Arduino debug output format:
# MODE	"RC" = manual RC override active, "JETSON" = autonomous control
# SPD	Current PWM output (0–255)
# DIR	"FWD" or "REV" (based on direction pin)
# STR	Steering servo angle (0–180)
# RCOK	1 if valid RC signal detected
# JETOK	1 if valid Jetson command received recently