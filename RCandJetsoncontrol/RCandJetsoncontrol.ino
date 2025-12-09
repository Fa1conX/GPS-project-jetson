// RC + Jetson Serial Motor/Steering Controller
// RC overrides Jetson until RC stays neutral for 2s

// --- Pin definitions ---
const int rcThrottlePin = 2;   // RC throttle input
const int rcSteeringPin = 3;   // RC steering input
const int dirPin = 4;          // Motor driver direction pin
const int pwmPin = 5;          // Motor driver PWM pin
const int servoPin = 6;        // Steering servo signal output

// --- RC calibration ---
const int minPulse = 1000;
const int neutral = 1500;
const int maxPulse = 2000;
const int deadband = 30;

// --- Deadband thresholds ---
#define MOTOR_DEADBAND 5  // Minimum speed to avoid buzzing
#define SERVO_DEADBAND 4  // Minimum angle change to avoid buzzing (increase for less buzzing)
#define SERVO_UPDATE_INTERVAL 25 // Minimum ms between servo updates

// --- Settings ---
float speedScalar = 0.8;
unsigned long signalTimeout = 100;     // stop if no RC signal within 100 ms
unsigned long jetsonTimeout = 500;     // stop if no Jetson command within 500 ms
unsigned long neutralHoldTime = 2000;  // must hold neutral this long to switch back to Jetson
unsigned long debugInterval = 500;     // how often to send debug info (ms)


// --- Tracking ---
unsigned long lastRCsignal = 0;
unsigned long lastJetsonCmd = 0;
unsigned long rcNeutralStart = 0;
unsigned long lastDebugTime = 0;
bool rcActive = true; // RC control mode initially

// --- Jetson command values ---
int jetsonThrottle = 0;  // 0–255
int jetsonSteering = 90; // 0–180 (centered)

// --- Binary protocol state machine ---
uint8_t pkt[6];
uint8_t pktIndex = 0;
bool receivingPacket = false;


// --- Includes ---
#include <Servo.h>
Servo steeringServo;

void setup() {
  pinMode(rcThrottlePin, INPUT);
  pinMode(rcSteeringPin, INPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(pwmPin, OUTPUT);
  steeringServo.attach(servoPin);
  Serial.begin(115200); // faster serial rate for Jetson
  // No custom PWM frequency for Arduino Nano; use default analogWrite
}

void loop() {
  // --- Step 1: Read RC input ---
  int thrPulse = pulseIn(rcThrottlePin, HIGH, 25000);
  int strPulse = pulseIn(rcSteeringPin, HIGH, 25000);
  bool rcSignalOK = (thrPulse > 0 && strPulse > 0);

  // --- Step 2: Nonblocking binary packet parser ---
  while (Serial.available()) {
      uint8_t b = Serial.read();

      if (!receivingPacket) {
          if (b == 0xAA) {       // Start byte
              receivingPacket = true;
              pktIndex = 0;
          }
          continue;
      }

      pkt[pktIndex++] = b;

      if (pktIndex >= 5) {
          // Expecting: [thr][steer][reserved][checksum][0x55]
          receivingPacket = false;  // done reading packet

          if (pkt[4] == 0x55) {     // Valid end byte?
              // Extract packet fields
              int throttle = (int8_t)pkt[0];   // signed
              int steering = pkt[1];           // unsigned
              int reserved = pkt[2];
              int checksum = pkt[3];

              int calc = ( (uint8_t)pkt[0] + pkt[1] + pkt[2] ) & 0xFF;

              if (calc == checksum) {
                  // Valid packet!
                  jetsonThrottle = constrain(throttle, -255, 255);
                  jetsonSteering = constrain(steering, 0, 180);
                  lastJetsonCmd = millis();
              }
          }
      }
  }




  // --- Step 3: Decide control mode ---

  // Throttle neutral = 1490–1550 µs
  bool rcThrottleNeutral = (thrPulse >= 1460 && thrPulse <= 1530);

  // Steering neutral = ±deadband around 1500
  bool rcSteeringNeutral = (abs(strPulse - neutral) <= deadband);

  bool rcIsNeutral = rcThrottleNeutral && rcSteeringNeutral;

  if (rcSignalOK) {
      lastRCsignal = millis();

      if (!rcIsNeutral) {
          // RC actively commanding → RC override immediately
          rcActive = true;
          rcNeutralStart = 0;   // reset timer
      } else {
          // RC is centered → begin counting neutral time
          if (rcNeutralStart == 0) {
              rcNeutralStart = millis();
          }

          // Stay in RC mode until neutralHoldTime passes
          if (millis() - rcNeutralStart > neutralHoldTime) {
              rcActive = false;   // Switch back to Jetson
          }
      }
  }


  // --- Step 4: Determine output values ---
  int speedValue = 0;
  bool direction = LOW;
  int steeringAngle = 90;

  if (rcActive && rcSignalOK) {
    // --- RC mode ---
    if (thrPulse > neutral + deadband) {
      direction = LOW;
      speedValue = map(thrPulse, neutral, maxPulse, 0, 255);
    } else if (thrPulse < neutral - deadband) {
      direction = HIGH;
      speedValue = map(thrPulse, neutral, minPulse, 0, 255);
    } else {
      speedValue = 0;
    }

    speedValue = constrain(speedValue * speedScalar, 0, 255);
    steeringAngle = map(strPulse, minPulse, maxPulse, 0, 180);
  } 
  else if (!rcActive && (millis() - lastJetsonCmd < jetsonTimeout)) {
    // --- Jetson mode ---
    direction = (jetsonThrottle >= 0) ? LOW : HIGH;
    speedValue = constrain(abs(jetsonThrottle), 0, 255);
    steeringAngle = constrain(jetsonSteering, 0, 180);
  } 
  else {
    // --- Failsafe ---
    speedValue = 0;
  }

  // --- Deadband logic for motor ---
  if (speedValue < MOTOR_DEADBAND) {
    speedValue = 0;  // Avoid small oscillations causing buzzing
  }

  // --- Improved deadband logic and update rate for servo ---
  static int lastServoAngle = 90;
  static unsigned long lastServoUpdate = 0;
  unsigned long nowMs = millis();
  if (abs(steeringAngle - lastServoAngle) > SERVO_DEADBAND && (nowMs - lastServoUpdate > SERVO_UPDATE_INTERVAL)) {
    steeringServo.write(steeringAngle);  // Only update if change is significant and enough time has passed
    lastServoAngle = steeringAngle;
    lastServoUpdate = nowMs;
  }

  // --- Step 5: Apply outputs ---
  digitalWrite(dirPin, direction);
  analogWrite(pwmPin, speedValue);
  // steeringServo.write(steeringAngle); // Already handled above

    // --- Step 6: Send debug info periodically ---
  unsigned long now = millis();
  if (now - lastDebugTime >= debugInterval) {
    lastDebugTime = now;

    Serial.print(now);
    Serial.print(" <MODE:");
    Serial.print(rcActive ? "RC" : "JETSON");
    Serial.print(";SPD:");
    Serial.print(speedValue);
    Serial.print(";DIR:");
    Serial.print(direction ? "REV" : "FWD");
    Serial.print(";STR:");
    Serial.print(steeringAngle);
    Serial.print(";RCOK:");
    Serial.print(rcSignalOK ? "1" : "0");
    Serial.print(";JETOK:");
    Serial.print((millis() - lastJetsonCmd < jetsonTimeout) ? "1" : "0");
    Serial.print(";thrPulse;");
    Serial.print(thrPulse);
    Serial.println(">");
  }

  delay(10);
}
