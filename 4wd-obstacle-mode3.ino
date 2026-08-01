#include <Servo.h>
#include <WiFiS3.h>
#include "arduino_secrets.h"

IPAddress laptopIP(192, 168, 0, 147);

const unsigned int ATLAS_UDP_DESTINATION_PORT = 4210;
const unsigned int ATLAS_UDP_LOCAL_PORT = 4211;
const unsigned long WIFI_RETRY_INTERVAL_MS = 5000;

WiFiUDP atlasUdp;

bool wifiTelemetryReady = false;
unsigned long lastWiFiRetryMs = 0;
bool remoteStopLatched = false;

enum AtlasControlMode {
  CONTROL_AUTO,
  CONTROL_MANUAL
};

AtlasControlMode controlMode = CONTROL_AUTO;

const unsigned long MANUAL_COMMAND_TIMEOUT_MS = 500;
unsigned long lastManualCommandMs = 0;
String lastManualCommand = "S";

class AtlasTelemetryPrint : public Print {
public:
  void begin(unsigned long baud) {
    Serial.begin(baud);
  }

  operator bool() {
    return static_cast<bool>(Serial);
  }

  size_t write(uint8_t value) override {
    Serial.write(value);

    if (value == '\n') {
      sendBufferedLine();
    } else if (value != '\r') {
      if (lineLength < sizeof(lineBuffer) - 1) {
        lineBuffer[lineLength++] = static_cast<char>(value);
      }
    }

    return 1;
  }

  using Print::write;

private:
  char lineBuffer[256];
  size_t lineLength = 0;

  void sendBufferedLine() {
    lineBuffer[lineLength] = '\0';

    if (lineLength > 0 &&
        wifiTelemetryReady &&
        WiFi.status() == WL_CONNECTED) {
      atlasUdp.beginPacket(laptopIP, ATLAS_UDP_DESTINATION_PORT);
      atlasUdp.write(
        reinterpret_cast<const uint8_t *>(lineBuffer),
        lineLength
      );
      atlasUdp.endPacket();
    }

    lineLength = 0;
  }
};

AtlasTelemetryPrint AtlasOut;

void startWiFiTelemetry() {
  AtlasOut.println();
  AtlasOut.println(F("Starting Atlas Wi-Fi telemetry"));
  AtlasOut.print(F("Connecting to Wi-Fi: "));
  AtlasOut.println(SECRET_SSID);

  int status = WL_IDLE_STATUS;
  unsigned long connectionStart = millis();

  while (status != WL_CONNECTED &&
         millis() - connectionStart < 20000UL) {
    status = WiFi.begin(SECRET_SSID, SECRET_PASS);

    if (status != WL_CONNECTED) {
      AtlasOut.println(F("Wi-Fi not connected yet - retrying"));
      delay(2000);
    }
  }

  if (status != WL_CONNECTED) {
    AtlasOut.println(F("Wi-Fi unavailable - continuing with USB Serial only"));
    wifiTelemetryReady = false;
    return;
  }

  AtlasOut.print(F("Waiting for Atlas IP"));

  unsigned long ipWaitStart = millis();

  while (WiFi.localIP().toString() == "0.0.0.0" &&
         millis() - ipWaitStart < 10000UL) {
    AtlasOut.print('.');
    delay(250);
  }

  AtlasOut.println();

  if (WiFi.localIP().toString() == "0.0.0.0") {
    AtlasOut.println(F("No IP assigned - continuing with USB Serial only"));
    wifiTelemetryReady = false;
    return;
  }

  atlasUdp.begin(ATLAS_UDP_LOCAL_PORT);
  wifiTelemetryReady = true;

  AtlasOut.println(F("Wi-Fi telemetry connected"));

  AtlasOut.print(F("Atlas IP: "));
  AtlasOut.println(WiFi.localIP());

  AtlasOut.print(F("Laptop destination: "));
  AtlasOut.print(laptopIP);
  AtlasOut.print(':');
  AtlasOut.println(ATLAS_UDP_DESTINATION_PORT);

  AtlasOut.print(F("Signal strength: "));
  AtlasOut.print(WiFi.RSSI());
  AtlasOut.println(F(" dBm"));
}

void maintainWiFiTelemetry() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiTelemetryReady &&
        WiFi.localIP().toString() != "0.0.0.0") {
      atlasUdp.begin(ATLAS_UDP_LOCAL_PORT);
      wifiTelemetryReady = true;
      AtlasOut.println(F("Wi-Fi telemetry restored"));
    }

    return;
  }

  wifiTelemetryReady = false;

  if (millis() - lastWiFiRetryMs < WIFI_RETRY_INTERVAL_MS) {
    return;
  }

  lastWiFiRetryMs = millis();
  AtlasOut.println(F("Wi-Fi disconnected - reconnecting"));

  WiFi.begin(SECRET_SSID, SECRET_PASS);
}



// Atlas Uno R4 + Sensor Shield V5 wiring

// HC-SR04 on Sensor Shield
#define Trig 7
#define Echo 8

// L298N motor driver
#define ENA 5
#define ENB 6
#define IN1 2
#define IN2 3
#define IN3 4
#define IN4 12

// Servo and IR sensors
#define SERVO_PIN          9
#define LEFT_IR_PIN        A0   // Front left
#define RIGHT_IR_PIN       A1   // Front right
#define LEFT_WING_IR_PIN   A2
#define RIGHT_WING_IR_PIN  A3
#define REAR_IR_PIN        A4

Servo atlasServo;

// Sensor state

float frontDistance = -1.0;
float lastGoodDistance = -1.0;

bool leftBlocked = false;
bool rightBlocked = false;
bool rearBlocked = false;
bool rightWingBlocked = false;
bool leftWingBlocked = false;

bool recoveryLocked = false;
bool lastFailedTurnLeft = false;
bool nextFallbackTurnLeft = true;

// Direction commitment prevents Atlas from immediately undoing a turn

int committedDirection = 0;
int commitmentRecoveriesRemaining = 0;

const int COMMITMENT_RECOVERIES = 2;
const float COMMITMENT_SWITCH_ADVANTAGE_CM = 45.0;

// Motor settings

const int MOTOR_SPEED = 125;
const int TURN_SPEED = 120;
const int CAUTIOUS_SPEED = 120;

// slowest speed before stopping
const int MIN_DRIVE_SPEED = 60;     
const float SLOW_START_CM = 80.0;    

const int WING_INNER_SPEED = 95;
const unsigned long WING_CORRECTION_MS = 110;

// Servo settings

const int SERVO_CENTER = 90;
const int SERVO_LEFT = 150;
const int SERVO_RIGHT = 30;

const int SERVO_LEFT_MID = 125;
const int SERVO_RIGHT_MID = 55;

const unsigned long SERVO_SETTLE_MS = 450;

// Distance settings

const float EMERGENCY_CM = 12.0;
const float OBSTACLE_CM = 42.0;
const float MIN_CLEAR_HEADING_CM = 60.0;
const float MIN_HEADING_TARGET_RATIO = 0.90;
const float MIN_TARGET_CLEARANCE_CM = 65.0;
const float MAX_TARGET_CLEARANCE_CM = 80.0;

// Reverse settings

const unsigned long NORMAL_BACK_TIME_MS = 650;
const unsigned long EMERGENCY_BACK_TIME_MS = 850;
const unsigned long CORNER_BACK_TIME_MS = 500;
const unsigned long BACK_CHECK_INTERVAL_MS = 35;

// Turn settings

const unsigned long BASE_TURN_TIME_MS = 410;
const unsigned long EXTRA_TURN_TIME_MS = 220;
const int MAX_TURN_EXTENSIONS = 5;

// IR debounce settings

const int IR_SAMPLE_COUNT = 5;
const int IR_BLOCKED_REQUIRED = 4;
const unsigned long IR_SAMPLE_DELAY_MS = 4;

// Startup settings

const int STARTUP_DISCARD_READINGS = 3;
const int STARTUP_VALID_READINGS = 5;

// Function declarations

bool readDebouncedBlocked(int pin);
void readIRSensors();
void printSensorState();

float readDistance();
float readStableDistance(int attempts);

float readDistanceAtAngle(int angle, const char *label);
float lookLeft();
float lookRight();
float lookCentre();
float scanLeftRegion();
float scanRightRegion();
float combineRegionReadings(float outerDistance, float innerDistance);
void centerServo();

void startupSensorStabilization();

void handleCentreObstacle();
void handleEmergency();
void handleBothFrontBlocked();
void handleLeftBlocked();
void handleRightBlocked();
void handleBothWingsBlocked();
void handleLeftWingBlocked();
void handleRightWingBlocked();

bool reverseForTime(unsigned long duration);

bool scanChooseAndTurn();
bool turnAndVerify(bool turnLeftDirection, float targetClearance);
bool verifyHeading(float targetClearance);

float calculateTargetClearance(float chosenDistance);

void handleRecoveryLock();

void forward(int speedValue = MOTOR_SPEED);
void back(int speedValue = MOTOR_SPEED);
void Left(int speedValue = TURN_SPEED);
void Right(int speedValue = TURN_SPEED);
void steerLeft();
void steerRight();
void STOP();

void setControlMode(AtlasControlMode newMode);
void reverseLeftManual();
void reverseRightManual();
void executeManualCommand(const String &command);
void checkForWiFiCommand();
void maintainManualSafety();

// Wi-Fi manual-control implementation

void setControlMode(AtlasControlMode newMode) {
  STOP();
  controlMode = newMode;
  lastManualCommand = "S";
  lastManualCommandMs = millis();

  if (controlMode == CONTROL_AUTO) {
    AtlasOut.println(F("CONTROL_MODE=AUTO"));
  } else {
    AtlasOut.println(F("CONTROL_MODE=MANUAL"));
  }
}

void reverseLeftManual() {
  analogWrite(ENA, WING_INNER_SPEED);
  analogWrite(ENB, MOTOR_SPEED);

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);

  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);

  AtlasOut.println(F("Reverse left"));
}

void reverseRightManual() {
  analogWrite(ENA, MOTOR_SPEED);
  analogWrite(ENB, WING_INNER_SPEED);

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);

  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);

  AtlasOut.println(F("Reverse right"));
}

void executeManualCommand(const String &command) {
  readIRSensors();

  if (command == "S") {
    STOP();
    lastManualCommand = "S";
    lastManualCommandMs = millis();
    AtlasOut.println(F("MANUAL_COMMAND=S"));
    return;
  }

  if (remoteStopLatched) {
    STOP();
    AtlasOut.println(F("MANUAL_REJECTED=ESTOP_LATCHED"));
    return;
  }

  if (controlMode != CONTROL_MANUAL) {
    STOP();
    AtlasOut.println(F("MANUAL_REJECTED=NOT_IN_MANUAL_MODE"));
    return;
  }

  bool frontAnyBlocked = leftBlocked || rightBlocked;
  bool frontLeftUnsafe = leftBlocked || leftWingBlocked;
  bool frontRightUnsafe = rightBlocked || rightWingBlocked;

  if (command == "F") {
    if (frontAnyBlocked) {
      STOP();
      AtlasOut.println(F("MANUAL_SAFETY_STOP=FRONT_BLOCKED"));
      return;
    }
    forward();
  } else if (command == "FL") {
    if (frontLeftUnsafe) {
      STOP();
      AtlasOut.println(F("MANUAL_SAFETY_STOP=FRONT_LEFT_BLOCKED"));
      return;
    }
    steerLeft();
  } else if (command == "FR") {
    if (frontRightUnsafe) {
      STOP();
      AtlasOut.println(F("MANUAL_SAFETY_STOP=FRONT_RIGHT_BLOCKED"));
      return;
    }
    steerRight();
  } else if (command == "L") {
    Left();
  } else if (command == "R") {
    Right();
  } else if (command == "B") {
    if (rearBlocked) {
      STOP();
      AtlasOut.println(F("MANUAL_SAFETY_STOP=REAR_BLOCKED"));
      return;
    }
    back();
  } else if (command == "BL") {
    if (rearBlocked) {
      STOP();
      AtlasOut.println(F("MANUAL_SAFETY_STOP=REAR_BLOCKED"));
      return;
    }
    reverseLeftManual();
  } else if (command == "BR") {
    if (rearBlocked) {
      STOP();
      AtlasOut.println(F("MANUAL_SAFETY_STOP=REAR_BLOCKED"));
      return;
    }
    reverseRightManual();
  } else {
    STOP();
    AtlasOut.println(F("MANUAL_COMMAND_UNKNOWN"));
    return;
  }

  lastManualCommand = command;
  lastManualCommandMs = millis();
  AtlasOut.print(F("MANUAL_COMMAND="));
  AtlasOut.println(command);
}

void checkForWiFiCommand() {
  if (!wifiTelemetryReady || WiFi.status() != WL_CONNECTED) return;

  int packetSize = atlasUdp.parsePacket();

  while (packetSize > 0) {
    char commandBuffer[32];
    int bytesRead = atlasUdp.read(commandBuffer, sizeof(commandBuffer) - 1);

    if (bytesRead > 0) {
      commandBuffer[bytesRead] = '\0';

      String command = String(commandBuffer);
      command.trim();
      command.toUpperCase();

      AtlasOut.print(F("REMOTE_COMMAND="));
      AtlasOut.println(command);

      if (command == "ESTOP" || command == "STOP") {
        remoteStopLatched = true;
        STOP();
        AtlasOut.println(F("REMOTE_STOP_LATCHED"));
      } else if (command == "CLEAR_ESTOP" || command == "RESUME") {
        STOP();
        remoteStopLatched = false;
        lastManualCommand = "S";
        lastManualCommandMs = millis();
        AtlasOut.println(F("REMOTE_STOP_CLEARED"));
      } else if (command == "AUTO") {
        setControlMode(CONTROL_AUTO);
      } else if (command == "MANUAL") {
        setControlMode(CONTROL_MANUAL);
      } else if (command == "PING") {
        AtlasOut.println(F("REMOTE_PONG"));
      } else if (
        command == "F"  || command == "FL" || command == "FR" ||
        command == "L"  || command == "R"  ||
        command == "B"  || command == "BL" || command == "BR" ||
        command == "S"
      ) {
        executeManualCommand(command);
      } else {
        AtlasOut.println(F("REMOTE_COMMAND_UNKNOWN"));
      }
    }

    packetSize = atlasUdp.parsePacket();
  }
}

void maintainManualSafety() {
  if (controlMode != CONTROL_MANUAL) return;

  if (remoteStopLatched) {
    STOP();
    return;
  }

  if (lastManualCommand != "S" &&
      millis() - lastManualCommandMs > MANUAL_COMMAND_TIMEOUT_MS) {
    STOP();
    lastManualCommand = "S";
    AtlasOut.println(F("MANUAL_WATCHDOG_STOP"));
  }
}

int calculateDriveSpeed(float distance) {

  if (distance < 0) {
    return CAUTIOUS_SPEED;
  }

  if (distance >= SLOW_START_CM) {
    return MOTOR_SPEED;
  }

  if (distance <= OBSTACLE_CM) {
    return MIN_DRIVE_SPEED;
  }

  return map(
    (int)distance,
    (int)OBSTACLE_CM,
    (int)SLOW_START_CM,
    MIN_DRIVE_SPEED,
    MOTOR_SPEED
  );
}

// Setup

void setup() {
  AtlasOut.begin(115200);
  delay(1200);
  startWiFiTelemetry();

  pinMode(Trig, OUTPUT);
  pinMode(Echo, INPUT);

  pinMode(LEFT_IR_PIN, INPUT);
  pinMode(RIGHT_IR_PIN, INPUT);
  pinMode(REAR_IR_PIN, INPUT);
  pinMode(RIGHT_WING_IR_PIN, INPUT);
  pinMode(LEFT_WING_IR_PIN, INPUT);

  pinMode(ENA, OUTPUT);
  pinMode(ENB, OUTPUT);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  digitalWrite(Trig, LOW);

  STOP();

  AtlasOut.println();
  AtlasOut.println(F("ATLAS UNO R4 BUILD"));
  AtlasOut.println(F("MODE TEST: region scan + committed turning"));
  AtlasOut.println(F("Starting in 5 seconds..."));

  delay(5000);

  atlasServo.attach(SERVO_PIN);
  atlasServo.write(SERVO_CENTER);
  delay(700);

  startupSensorStabilization();

  AtlasOut.println(F("Atlas started"));
  AtlasOut.println(F("CONTROL_MODE=AUTO"));
}

// Main loop

void loop() {
  maintainWiFiTelemetry();
  checkForWiFiCommand();
  maintainManualSafety();

  if (remoteStopLatched) {
    STOP();
    delay(50);
    return;
  }

  if (controlMode == CONTROL_MANUAL) {
    readIRSensors();
    frontDistance = readDistance();

    if (frontDistance >= 0) {
      lastGoodDistance = frontDistance;
    }

    printSensorState();
    delay(100);
    return;
  }

  readIRSensors();

  if (recoveryLocked) {
    handleRecoveryLock();
    return;
  }

  if (leftBlocked && rightBlocked) {
    handleBothFrontBlocked();
    return;
  }

  if (leftBlocked && !rightBlocked) {
    handleLeftBlocked();
    return;
  }

  if (!leftBlocked && rightBlocked) {
    handleRightBlocked();
    return;
  }

  if (leftWingBlocked && rightWingBlocked) {
    handleBothWingsBlocked();
    return;
  }

  if (leftWingBlocked && !rightWingBlocked) {
    handleLeftWingBlocked();
    return;
  }

  if (!leftWingBlocked && rightWingBlocked) {
    handleRightWingBlocked();
    return;
  }

  frontDistance = readDistance();

  if (frontDistance >= 0) {
    lastGoodDistance = frontDistance;
  }

  printSensorState();

  if (frontDistance >= 0 && frontDistance <= EMERGENCY_CM) {
    handleEmergency();
    return;
  }

  if (frontDistance >= 0 && frontDistance < OBSTACLE_CM) {
    handleCentreObstacle();
    return;
  }

  if (frontDistance < 0) {
    AtlasOut.println(F("NO ECHO + front IR clear -> cautious forward"));
    forward(CAUTIOUS_SPEED);
    delay(100);
    return;
  }

  int driveSpeed = calculateDriveSpeed(frontDistance);

  AtlasOut.print(F("Drive speed: "));
  AtlasOut.println(driveSpeed);

  forward(driveSpeed);
  delay(100);
}

// IR sensors
// LOW = blocked, HIGH = clear

bool readDebouncedBlocked(int pin) {
  int blockedSamples = 0;

  for (int i = 0; i < IR_SAMPLE_COUNT; i++) {
    if (digitalRead(pin) == LOW) {
      blockedSamples++;
    }

    delay(IR_SAMPLE_DELAY_MS);
  }

  return blockedSamples >= IR_BLOCKED_REQUIRED;
}

void readIRSensors() {
  leftBlocked = readDebouncedBlocked(LEFT_IR_PIN);
  rightBlocked = readDebouncedBlocked(RIGHT_IR_PIN);
  rearBlocked = readDebouncedBlocked(REAR_IR_PIN);
  rightWingBlocked = readDebouncedBlocked(RIGHT_WING_IR_PIN);
  leftWingBlocked = readDebouncedBlocked(LEFT_WING_IR_PIN);
}

// Serial output

void printSensorState() {
  AtlasOut.print(F("Distance="));

  if (frontDistance < 0) {
    AtlasOut.print(F("NO_ECHO"));
  } else {
    AtlasOut.print(frontDistance);
    AtlasOut.print(F("cm"));
  }

  AtlasOut.print(F(" | FRONT_LEFT="));
  AtlasOut.print(leftBlocked ? F("BLOCKED") : F("CLEAR"));

  AtlasOut.print(F(" | FRONT_RIGHT="));
  AtlasOut.print(rightBlocked ? F("BLOCKED") : F("CLEAR"));

  AtlasOut.print(F(" | REAR="));
  AtlasOut.print(rearBlocked ? F("BLOCKED") : F("CLEAR"));

  AtlasOut.print(F(" | LEFT_WING="));
  AtlasOut.print(leftWingBlocked ? F("BLOCKED") : F("CLEAR"));

  AtlasOut.print(F(" | RIGHT_WING="));
  AtlasOut.println(rightWingBlocked ? F("BLOCKED") : F("CLEAR"));
}

// HC-SR04

float readDistance() {
  digitalWrite(Trig, LOW);
  delayMicroseconds(5);

  digitalWrite(Trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(Trig, LOW);

  unsigned long echoTime = pulseIn(Echo, HIGH, 40000UL);

  if (echoTime == 0) {
    return -1.0;
  }

  float distance = echoTime * 0.0343 / 2.0;

  if (distance < 2.0 || distance > 300.0) {
    return -1.0;
  }

  return distance;
}

float readStableDistance(int attempts) {
  float total = 0.0;
  int validCount = 0;

  for (int i = 0; i < attempts; i++) {
    float reading = readDistance();

    if (reading >= 0) {
      total += reading;
      validCount++;
    }

    delay(35);
  }

  if (validCount == 0) {
    return -1.0;
  }

  return total / validCount;
}

// Startup stabilization

void startupSensorStabilization() {
  AtlasOut.println(F("Stabilizing sensors..."));

  centerServo();

  for (int i = 0; i < STARTUP_DISCARD_READINGS; i++) {
    readDistance();
    delay(60);
  }

  float startupDistance = readStableDistance(STARTUP_VALID_READINGS);

  readIRSensors();

  AtlasOut.print(F("Startup distance = "));

  if (startupDistance < 0) {
    AtlasOut.println(F("NO ECHO - accepted as unknown/open"));
  } else {
    AtlasOut.print(startupDistance);
    AtlasOut.println(F(" cm"));
    lastGoodDistance = startupDistance;
  }

  printSensorState();
}

// Servo scanning

float readDistanceAtAngle(int angle, const char *label) {
  atlasServo.write(angle);
  delay(SERVO_SETTLE_MS);

  float distance = readStableDistance(3);

  AtlasOut.print(label);
  AtlasOut.print(F(" = "));

  if (distance < 0) {
    AtlasOut.println(F("NO ECHO"));
  } else {
    AtlasOut.print(distance);
    AtlasOut.println(F(" cm"));
  }

  return distance;
}

float lookLeft() {
  return readDistanceAtAngle(SERVO_LEFT, "Left scan");
}

float lookRight() {
  return readDistanceAtAngle(SERVO_RIGHT, "Right scan");
}

float lookCentre() {
  return readDistanceAtAngle(SERVO_CENTER, "Centre scan");
}

float combineRegionReadings(float outerDistance, float innerDistance) {
  if (outerDistance < 0 && innerDistance < 0) {
    return -1.0;
  }

  if (outerDistance < 0) {
    return innerDistance;
  }

  if (innerDistance < 0) {
    return outerDistance;
  }

  return min(outerDistance, innerDistance);
}

float scanLeftRegion() {
  float outerDistance = readDistanceAtAngle(SERVO_LEFT, "Left outer scan");
  float innerDistance = readDistanceAtAngle(SERVO_LEFT_MID, "Left inner scan");
  float regionDistance = combineRegionReadings(outerDistance, innerDistance);

  AtlasOut.print(F("Left scan = "));
  if (regionDistance < 0) {
    AtlasOut.println(F("NO ECHO"));
  } else {
    AtlasOut.print(regionDistance);
    AtlasOut.println(F(" cm"));
  }

  return regionDistance;
}

float scanRightRegion() {
  float innerDistance = readDistanceAtAngle(SERVO_RIGHT_MID, "Right inner scan");
  float outerDistance = readDistanceAtAngle(SERVO_RIGHT, "Right outer scan");
  float regionDistance = combineRegionReadings(outerDistance, innerDistance);

  AtlasOut.print(F("Right scan = "));
  if (regionDistance < 0) {
    AtlasOut.println(F("NO ECHO"));
  } else {
    AtlasOut.print(regionDistance);
    AtlasOut.println(F(" cm"));
  }

  return regionDistance;
}

void centerServo() {
  atlasServo.write(SERVO_CENTER);
  delay(350);
}

// Obstacle handlers

void handleCentreObstacle() {
  AtlasOut.println(F("Centre obstacle detected"));

  STOP();
  delay(150);

  reverseForTime(NORMAL_BACK_TIME_MS);

  if (!scanChooseAndTurn()) {
    recoveryLocked = true;
    AtlasOut.println(F("Escape failed - forward movement locked"));
  }
}

void handleEmergency() {
  AtlasOut.println(F("Emergency centre obstacle"));

  STOP();
  delay(150);

  reverseForTime(EMERGENCY_BACK_TIME_MS);

  if (!scanChooseAndTurn()) {
    recoveryLocked = true;
    AtlasOut.println(F("Emergency escape failed - locked"));
  }
}

void handleBothFrontBlocked() {
  AtlasOut.println(F("Both front IR sensors blocked"));

  STOP();
  delay(150);

  reverseForTime(EMERGENCY_BACK_TIME_MS);

  if (!scanChooseAndTurn()) {
    recoveryLocked = true;
    AtlasOut.println(F("Front escape failed - locked"));
  }
}

void handleLeftBlocked() {
  AtlasOut.println(F("Front left blocked - escape RIGHT"));

  STOP();
  delay(120);

  reverseForTime(CORNER_BACK_TIME_MS);

  bool success = turnAndVerify(false, MIN_TARGET_CLEARANCE_CM);

  if (!success) {
    lastFailedTurnLeft = false;
    recoveryLocked = true;
    AtlasOut.println(F("RIGHT escape failed - forward locked"));
  }
}

void handleRightBlocked() {
  AtlasOut.println(F("Front right blocked - escape LEFT"));

  STOP();
  delay(120);

  reverseForTime(CORNER_BACK_TIME_MS);

  bool success = turnAndVerify(true, MIN_TARGET_CLEARANCE_CM);

  if (!success) {
    lastFailedTurnLeft = true;
    recoveryLocked = true;
    AtlasOut.println(F("LEFT escape failed - forward locked"));
  }
}

// Wing handlers

void handleLeftWingBlocked() {
  AtlasOut.println(F("Left wing near wall - gentle correction RIGHT"));
  steerRight();
  delay(WING_CORRECTION_MS);
}

void handleRightWingBlocked() {
  AtlasOut.println(F("Right wing near wall - gentle correction LEFT"));
  steerLeft();
  delay(WING_CORRECTION_MS);
}

void handleBothWingsBlocked() {
  AtlasOut.println(F("Both wings blocked - full recovery"));

  STOP();
  delay(150);

  bool reversed = reverseForTime(CORNER_BACK_TIME_MS);

  if (!reversed) {
    recoveryLocked = true;
    AtlasOut.println(F("Wing recovery reverse failed - locked"));
    return;
  }

  if (!scanChooseAndTurn()) {
    recoveryLocked = true;
    AtlasOut.println(F("Wing escape failed - forward locked"));
  }
}

// Rear-protected reverse

bool reverseForTime(unsigned long duration) {
  readIRSensors();

  if (rearBlocked) {
    AtlasOut.println(F("Rear blocked - reverse cancelled"));
    STOP();
    return false;
  }

  AtlasOut.print(F("Reverse target = "));
  AtlasOut.print(duration);
  AtlasOut.println(F(" ms"));

  unsigned long startTime = millis();

  back();

  while (millis() - startTime < duration) {
    delay(BACK_CHECK_INTERVAL_MS);

    rearBlocked = readDebouncedBlocked(REAR_IR_PIN);

    if (rearBlocked) {
      AtlasOut.println(F("Rear obstacle detected - reverse stopped"));
      STOP();
      delay(180);
      return false;
    }
  }

  STOP();
  delay(220);

  AtlasOut.println(F("Reverse completed"));
  return true;
}

// Scan and choose direction

bool scanChooseAndTurn() {
  STOP();
  delay(120);

  float leftDistance = scanLeftRegion();
  float rightDistance = scanRightRegion();

  centerServo();
  readIRSensors();

  bool leftValid = leftDistance >= 0;
  bool rightValid = rightDistance >= 0;

  bool leftSideBlocked = leftBlocked || leftWingBlocked;
  bool rightSideBlocked = rightBlocked || rightWingBlocked;

  bool chooseLeft = false;
  bool usedCommitment = false;
  float chosenDistance = -1.0;

  if (leftSideBlocked && !rightSideBlocked) {
    chooseLeft = false;
    chosenDistance = rightValid ? rightDistance : 70.0;
    committedDirection = -1;
    commitmentRecoveriesRemaining = COMMITMENT_RECOVERIES;
    AtlasOut.println(F("Left IR blocked - choosing RIGHT"));
  } else if (!leftSideBlocked && rightSideBlocked) {
    chooseLeft = true;
    chosenDistance = leftValid ? leftDistance : 70.0;
    committedDirection = 1;
    commitmentRecoveriesRemaining = COMMITMENT_RECOVERIES;
    AtlasOut.println(F("Right IR blocked - choosing LEFT"));
  } else if (leftValid && rightValid) {
    if (commitmentRecoveriesRemaining > 0 && committedDirection != 0) {
      float committedDistance = committedDirection > 0 ? leftDistance : rightDistance;
      float oppositeDistance = committedDirection > 0 ? rightDistance : leftDistance;

      bool committedBlocked = committedDirection > 0 ? leftSideBlocked : rightSideBlocked;
      bool oppositeMuchBetter =
        oppositeDistance >= committedDistance + COMMITMENT_SWITCH_ADVANTAGE_CM;

      if (!committedBlocked && !oppositeMuchBetter) {
        chooseLeft = committedDirection > 0;
        chosenDistance = committedDistance;
        commitmentRecoveriesRemaining--;
        usedCommitment = true;

        AtlasOut.println(chooseLeft
          ? F("LEFT selected - commitment")
          : F("RIGHT selected - commitment"));
      } else {
        chooseLeft = oppositeDistance > committedDistance
          ? committedDirection < 0
          : committedDirection > 0;
        chosenDistance = chooseLeft ? leftDistance : rightDistance;
        committedDirection = chooseLeft ? 1 : -1;
        commitmentRecoveriesRemaining = COMMITMENT_RECOVERIES;

        AtlasOut.println(chooseLeft
          ? F("LEFT selected - strong advantage")
          : F("RIGHT selected - strong advantage"));
      }
    } else {
      chooseLeft = leftDistance >= rightDistance;
      chosenDistance = chooseLeft ? leftDistance : rightDistance;
      committedDirection = chooseLeft ? 1 : -1;
      commitmentRecoveriesRemaining = COMMITMENT_RECOVERIES;

      AtlasOut.println(chooseLeft ? F("LEFT selected") : F("RIGHT selected"));
    }
  } else if (leftValid) {
    chooseLeft = true;
    chosenDistance = leftDistance;
    committedDirection = 1;
    commitmentRecoveriesRemaining = COMMITMENT_RECOVERIES;
    AtlasOut.println(F("Only LEFT scan valid - choosing LEFT"));
  } else if (rightValid) {
    chooseLeft = false;
    chosenDistance = rightDistance;
    committedDirection = -1;
    commitmentRecoveriesRemaining = COMMITMENT_RECOVERIES;
    AtlasOut.println(F("Only RIGHT scan valid - choosing RIGHT"));
  } else {
    if (commitmentRecoveriesRemaining > 0 && committedDirection != 0) {
      chooseLeft = committedDirection > 0;
      commitmentRecoveriesRemaining--;
      usedCommitment = true;
      AtlasOut.println(chooseLeft
        ? F("Both scans NO ECHO - committed LEFT")
        : F("Both scans NO ECHO - committed RIGHT"));
    } else {
      chooseLeft = nextFallbackTurnLeft;
      nextFallbackTurnLeft = !nextFallbackTurnLeft;
      committedDirection = chooseLeft ? 1 : -1;
      commitmentRecoveriesRemaining = COMMITMENT_RECOVERIES;
      AtlasOut.println(F("Both scans NO ECHO - fallback direction"));
    }

    chosenDistance = 70.0;
  }

  float targetClearance = calculateTargetClearance(chosenDistance);

  AtlasOut.print(F("Chosen distance = "));
  AtlasOut.print(chosenDistance);
  AtlasOut.println(F(" cm"));

  AtlasOut.print(F("Heading target = "));
  AtlasOut.print(targetClearance);
  AtlasOut.println(F(" cm"));

  if (usedCommitment) {
    AtlasOut.print(F("Commitment recoveries remaining = "));
    AtlasOut.println(commitmentRecoveriesRemaining);
  }

  bool success = turnAndVerify(chooseLeft, targetClearance);

  if (success) {
    recoveryLocked = false;
    return true;
  }

  lastFailedTurnLeft = chooseLeft;

  AtlasOut.println(F("Chosen direction failed - remaining committed"));

  STOP();
  return false;
}

// Clearance target

float calculateTargetClearance(float chosenDistance) {
  if (chosenDistance < 0) {
    return MIN_TARGET_CLEARANCE_CM;
  }

  float target = chosenDistance * 0.45;

  if (target < MIN_TARGET_CLEARANCE_CM) {
    target = MIN_TARGET_CLEARANCE_CM;
  }

  if (target > MAX_TARGET_CLEARANCE_CM) {
    target = MAX_TARGET_CLEARANCE_CM;
  }

  return target;
}

// Continuous turn and verification

bool turnAndVerify(bool turnLeftDirection, float targetClearance) {
  AtlasOut.print(turnLeftDirection ? F("Continuous LEFT turn") : F("Continuous RIGHT turn"));
  AtlasOut.print(F(" | target="));
  AtlasOut.print(targetClearance);
  AtlasOut.println(F(" cm"));

  centerServo();

  if (turnLeftDirection) {
    Left();
  } else {
    Right();
  }

  delay(BASE_TURN_TIME_MS);

  STOP();
  delay(220);

  if (verifyHeading(targetClearance)) {
    return true;
  }

  for (int attempt = 1; attempt <= MAX_TURN_EXTENSIONS; attempt++) {
    AtlasOut.print(F("Turn extension "));
    AtlasOut.print(attempt);
    AtlasOut.print(F("/"));
    AtlasOut.println(MAX_TURN_EXTENSIONS);

    if (turnLeftDirection) {
      Left();
    } else {
      Right();
    }

    delay(EXTRA_TURN_TIME_MS);

    STOP();
    delay(220);

    if (verifyHeading(targetClearance)) {
      return true;
    }
  }

  AtlasOut.println(F("Direction could not be verified"));

  STOP();
  return false;
}

// Heading verification

bool verifyHeading(float targetClearance) {
  centerServo();
  readIRSensors();

  float checkDistance = readStableDistance(3);

  AtlasOut.print(F("Heading check = "));

  if (checkDistance < 0) {
    AtlasOut.print(F("NO ECHO"));
  } else {
    AtlasOut.print(checkDistance);
    AtlasOut.print(F(" cm"));
  }

  AtlasOut.print(F(" | FRONT_LEFT="));
  AtlasOut.print(leftBlocked ? F("BLOCKED") : F("CLEAR"));

  AtlasOut.print(F(" | FRONT_RIGHT="));
  AtlasOut.println(rightBlocked ? F("BLOCKED") : F("CLEAR"));

  if (leftBlocked || rightBlocked) {
    AtlasOut.println(F("Heading rejected: front IR blocked"));
    return false;
  }

  if (checkDistance < 0) {
    AtlasOut.println(F("Heading rejected: NO ECHO is uncertain"));
    return false;
  }

  if (checkDistance >= targetClearance) {
    AtlasOut.println(F("Heading target reached"));
    lastGoodDistance = checkDistance;
    recoveryLocked = false;
    return true;
  }

  float minimumUsable = targetClearance * MIN_HEADING_TARGET_RATIO;

  if (minimumUsable < MIN_CLEAR_HEADING_CM) {
    minimumUsable = MIN_CLEAR_HEADING_CM;
  }

  if (checkDistance >= minimumUsable) {
    AtlasOut.println(F("Heading accepted within target tolerance"));
    lastGoodDistance = checkDistance;
    recoveryLocked = false;
    return true;
  }

  AtlasOut.print(F("Heading still too close; need at least "));
  AtlasOut.print(minimumUsable);
  AtlasOut.println(F(" cm"));

  return false;
}

// Recovery lock

void handleRecoveryLock() {
  AtlasOut.println(F("RECOVERY LOCK - normal forward disabled"));

  STOP();
  delay(200);

  readIRSensors();

  if (leftBlocked && rightBlocked) {
    reverseForTime(EMERGENCY_BACK_TIME_MS);
  } else if (leftBlocked || rightBlocked) {
    reverseForTime(CORNER_BACK_TIME_MS);
  }

  if (scanChooseAndTurn()) {
    AtlasOut.println(F("Recovery lock cleared"));
    recoveryLocked = false;
    return;
  }

  AtlasOut.println(F("Recovery still unresolved"));

  STOP();
  delay(500);
}

// Motor functions

void forward(int speedValue) {
  analogWrite(ENA, speedValue);
  analogWrite(ENB, speedValue);

  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);

  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);

  AtlasOut.println(F("Forward"));
}

void back(int speedValue) {
  analogWrite(ENA, speedValue);
  analogWrite(ENB, speedValue);

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);

  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);

  AtlasOut.println(F("Back"));
}

void Left(int speedValue) {
  analogWrite(ENA, speedValue);
  analogWrite(ENB, speedValue);

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);

  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);

  AtlasOut.println(F("Left"));
}

void Right(int speedValue) {
  analogWrite(ENA, speedValue);
  analogWrite(ENB, speedValue);

  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);

  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);

  AtlasOut.println(F("Right"));
}

void steerLeft() {
  analogWrite(ENA, WING_INNER_SPEED);
  analogWrite(ENB, MOTOR_SPEED);

  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);

  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);

  AtlasOut.println(F("Steer left"));
}

void steerRight() {
  analogWrite(ENA, MOTOR_SPEED);
  analogWrite(ENB, WING_INNER_SPEED);

  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);

  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);

  AtlasOut.println(F("Steer right"));
}

void STOP() {
  analogWrite(ENA, 0);
  analogWrite(ENB, 0);

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);

  AtlasOut.println(F("STOP"));
}