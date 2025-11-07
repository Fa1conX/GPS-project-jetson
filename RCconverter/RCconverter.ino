// RC Receiver → Motor Driver Converter
// Direction: HIGH = Forward, LOW = Reverse
// Includes sensitivity control and signal timeout failsafe

const int rcPin = 2;     // RC input pin
const int dirPin = 4;    // Direction output to motor driver
const int pwmPin = 5;    // PWM speed output to motor driver

// RC input calibration (microseconds)
const int minPulse = 1000;    // Full reverse
const int neutral = 1500;     // Stick center
const int maxPulse = 2000;    // Full forward

// Adjustable sensitivity (0.0–1.0)
// 1.0 = full power, 0.5 = half power, etc.
float speedScalar = 0.8;

// Deadband around neutral (µs)
const int deadband = 25;

// Failsafe timeout in milliseconds
const unsigned long signalTimeout = 100;  // stop if no signal within 100 ms

// For tracking signal timing
unsigned long lastSignalTime = 0;

void setup() {
  pinMode(rcPin, INPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(pwmPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  // Read pulse width from RC receiver
  int pulseWidth = pulseIn(rcPin, HIGH, 25000); // 25 ms timeout (≈ 2 frames)

  if (pulseWidth > 0) {
    // Got a valid signal, update last time seen
    lastSignalTime = millis();

    int speedValue = 0;
    bool direction = HIGH;

    if (pulseWidth > neutral + deadband) {
      // Forward motion
      direction = LOW;
      speedValue = map(pulseWidth, neutral, maxPulse, 0, 255);
    } 
    else if (pulseWidth < neutral - deadband) {
      // Reverse motion
      direction = HIGH;
      speedValue = map(pulseWidth, neutral, minPulse, 0, 255);
    } 
    else {
      // Within deadband — stop
      speedValue = 0;
    }

    // Apply sensitivity
    speedValue = constrain(speedValue * speedScalar, 0, 255);

    // Output to motor driver
    digitalWrite(dirPin, direction);
    analogWrite(pwmPin, speedValue);
  }

  // Check for lost signal
  if (millis() - lastSignalTime > signalTimeout) {
    // No signal recently — stop motor
    analogWrite(pwmPin, 0);
  }

  // Debug output
  //Serial.print("Pulse: "); Serial.print(pulseWidth);
  //Serial.print("  Dir: "); Serial.print(digitalRead(dirPin) ? "FWD" : "REV");
  //Serial.print("  Speed: "); Serial.print(analogRead(pwmPin));
  //Serial.print("  Signal age: "); Serial.println(millis() - lastSignalTime);

  delay(10);
}
