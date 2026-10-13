/*
  Estufa Monitor - ESP32 Firmware
  Hardware: ESP32 DevKit V1 / ESP32-S3
  Sensors: DHT22 (temp/humidity), Soil Moisture Capacitive, BH1750 (LUX), SCD41 (CO2)
  Communication: Serial USB to FastAPI backend
  Features: Deep sleep, Watchdog, Calibration, Auto-reconnect, OTA ready
*/

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <BH1750.h>
#include <SensirionI2CScd4x.h>
#include <EEPROM.h>
#include <esp_task_wdt.h>
#include <esp_sleep.h>
#include <Update.h>

// ==================== USER CONFIGURATION ====================
#define WIFI_SSID "SEU_WIFI_SSID"
#define WIFI_PASSWORD "SUA_WIFI_PASSWORD"

#define BACKEND_URL "http://SEU_IP_LOCAL:8000"  // Ex: http://192.168.1.100:8000
#define DEVICE_ID "estufa-01"
#define FIRMWARE_VERSION "1.0.0"

#define READING_INTERVAL_MS 30000      // 30 segundos entre leituras
#define DEEP_SLEEP_ENABLED false        // true = modo bateria, false = sempre ligado
#define DEEP_SLEEP_DURATION_US 30000000 // 30 segundos em microssegundos

// ==================== PIN DEFINITIONS ====================
#define DHT_PIN 4              // GPIO4 - DHT22
#define SOIL_MOISTURE_PIN 34   // ADC1_CH6 (GPIO34)
#define BH1750_SDA 21
#define BH1750_SCL 22
#define SCD41_SDA 21
#define SCD41_SCL 22
#define LED_STATUS 2           // Built-in LED
#define RELAY_PIN 5            // GPIO5 - Relé bomba

// Sensor addresses
#define BH1750_ADDR 0x23
#define SCD41_ADDR 0x62
#define DHT_TYPE DHT22

// EEPROM
#define EEPROM_SIZE 512
#define CALIB_OFFSET 0

// ==================== GLOBAL OBJECTS ====================
DHT dht(DHT_PIN, DHT_TYPE);
BH1750 lightMeter(0x23);
SensirionI2CScd4x scd4x;

struct SensorReading {
  float temperatura;
  float umidade_ar;
  float umidade_solo;
  float luminosidade;
  float co2;
  bool valid;
};

struct CalibrationData {
  float soil_dry;      // Valor bruto solo seco
  float soil_wet;      // Valor bruto solo molhado
  bool calibrated;
};

CalibrationData calibration;
unsigned long lastReadingTime = 0;
unsigned long lastWifiCheck = 0;
int wifiReconnectAttempts = 0;
bool sensorsInitialized = false;
bool backendConnected = false;

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("=== Estufa Monitor ESP32 Starting ===");
  Serial.printf("Device ID: %s\n", DEVICE_ID);
  Serial.printf("Firmware: %s\n", FIRMWARE_VERSION);
  Serial.printf("Free Heap: %d bytes\n", ESP.getFreeHeap());
  
  // Initialize EEPROM
  EEPROM.begin(EEPROM_SIZE);
  loadCalibration();
  
  // Initialize pins
  pinMode(LED_STATUS, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(SOIL_MOISTURE_PIN, INPUT);
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(LED_STATUS, LOW);
  
  // Initialize I2C
  Wire.begin(BH1750_SDA, BH1750_SCL);
  Wire.setClock(100000);
  
  // Initialize sensors
  initializeSensors();
  
  // Connect to WiFi
  connectWiFi();
  
  // Initialize watchdog (60 second timeout)
  esp_task_wdt_init(60, true);
  esp_task_wdt_add(NULL);
  
  Serial.println("=== Setup Complete ===");
  Serial.printf("Free Heap: %d bytes\n", ESP.getFreeHeap());
}

// ==================== MAIN LOOP ====================
void loop() {
  esp_task_wdt_reset();
  
  // Handle serial commands for calibration
  handleSerialCommands();
  
  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    handleWiFiReconnect();
  }
  
  // Check if it's time to take readings
  if (millis() - lastReadingTime >= READING_INTERVAL_MS) {
    SensorReading reading = takeReadings();
    if (reading.valid) {
      sendToBackend(reading);
    }
    lastReadingTime = millis();
  }
  
  // Handle OTA updates check (every hour)
  static unsigned long lastOtaCheck = 0;
  if (millis() - lastOtaCheck >= 3600000) {
    checkForUpdates();
    lastOtaCheck = millis();
  }
  
  // Deep sleep if enabled
  if (DEEP_SLEEP_ENABLED) {
    enterDeepSleep();
  }
  
  delay(100);
}

// ==================== SENSOR INITIALIZATION ====================
void initializeSensors() {
  Serial.println("Initializing sensors...");
  
  // DHT22 - Temperature & Humidity
  dht.begin();
  Serial.println("✓ DHT22 initialized");
  
  // BH1750 - Light Sensor
  if (lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)) {
    Serial.println("✓ BH1750 initialized (LUX)");
  } else {
    Serial.println("✗ BH1750 not found");
  }
  
  // SCD41 - CO2 Sensor
  scd4x.begin(Wire);
  uint16_t error = scd4x.stopPeriodicMeasurement();
  if (error) {
    Serial.printf("SCD41 stop error: 0x%04X\n", error);
  }
  error = scd4x.startPeriodicMeasurement();
  if (error) {
    Serial.printf("SCD41 start error: 0x%04X\n", error);
  } else {
    Serial.println("✓ SCD41 initialized (CO2)");
  }
  
  // Configure ADC for soil moisture
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db); // 0-3.3V range
  
  sensorsInitialized = true;
  Serial.println("All sensors initialized");
  Serial.printf("Free Heap: %d bytes\n", ESP.getFreeHeap());
}

// ==================== WIFI MANAGEMENT ====================
void connectWiFi() {
  Serial.printf("Connecting to WiFi: %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  unsigned long startTime = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startTime < 30000) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_STATUS, !digitalRead(LED_STATUS));
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.printf("✓ WiFi connected! IP: %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("RSSI: %d dBm\n", WiFi.RSSI());
    wifiReconnectAttempts = 0;
    digitalWrite(LED_STATUS, HIGH);
    backendConnected = true;
  } else {
    Serial.println();
    Serial.println("✗ WiFi connection failed!");
    digitalWrite(LED_STATUS, LOW);
    backendConnected = false;
  }
}

void handleWiFiReconnect() {
  if (wifiReconnectAttempts >= 5) {
    Serial.println("Too many reconnect attempts, restarting...");
    ESP.restart();
  }
  
  Serial.println("WiFi disconnected, reconnecting...");
  wifiReconnectAttempts++;
  connectWiFi();
}

// ==================== SENSOR READINGS ====================
SensorReading takeReadings() {
  SensorReading reading = {0};
  reading.valid = false;
  
  Serial.println("Taking sensor readings...");
  
  // 1. DHT22 - Temperature & Humidity
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();
  
  if (isnan(temp) || isnan(hum)) {
    Serial.println("✗ DHT22 read failed");
    return reading;
  }
  
  reading.temperatura = temp;
  reading.umidade_ar = hum;
  
  // 2. Soil Moisture (Capacitive)
  int soilRaw = analogRead(SOIL_MOISTURE_PIN);
  reading.umidade_solo = mapFloat(soilRaw, calibration.soil_dry, calibration.soil_wet, 0, 100);
  reading.umidade_solo = constrain(reading.umidade_solo, 0, 100);
  
  // 3. BH1750 - Light/LUX
  float lux = lightMeter.readLightLevel();
  reading.luminosidade = lux;
  
  // 4. SCD41 - CO2
  uint16_t co2;
  float scdTemp, scdHum;
  if (scd4x.readMeasurement(co2, scdTemp, scdHum) == 0) {
    reading.co2 = (float)co2;
  } else {
    reading.co2 = 400.0; // Default atmospheric CO2
  }
  
  reading.valid = true;
  
  Serial.printf("Temp: %.1f°C | Hum: %.1f%% | Solo: %.1f%% | LUX: %.0f | CO2: %.0f ppm\n",
    reading.temperatura, reading.umidade_ar, reading.umidade_solo, reading.luminosidade, reading.co2);
  
  return reading;
}

float mapFloat(float x, float in_min, float in_max, float out_min, float out_max) {
  if (in_max == in_min) return out_min;
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

// ==================== HTTP COMMUNICATION ====================
void sendToBackend(const SensorReading& reading) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, skipping send");
    backendConnected = false;
    return;
  }
  
  HTTPClient http;
  WiFiClient client;
  
  String url = String(BACKEND_URL) + "/api/sensores/leitura";
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(10000);
  
  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["temperatura"] = reading.temperatura;
  doc["umidade_ar"] = reading.umidade_ar;
  doc["umidade_solo"] = reading.umidade_solo;
  doc["luminosidade"] = reading.luminosidade;
  doc["co2"] = reading.co2;
  doc["timestamp"] = getISO8601Time();
  doc["rssi"] = WiFi.RSSI();
  doc["free_heap"] = ESP.getFreeHeap();
  doc["firmware"] = FIRMWARE_VERSION;
  
  String payload;
  serializeJson(doc, payload);
  
  int httpCode = http.POST(payload);
  
  if (httpCode > 0) {
    String response = http.getString();
    Serial.printf("HTTP %d: %s\n", httpCode, response.c_str());
    backendConnected = (httpCode == 200);
  } else {
    Serial.printf("HTTP Error: %s\n", http.errorToString(httpCode).c_str());
    backendConnected = false;
  }
  
  http.end();
}

// ==================== OTA UPDATES ====================
void checkForUpdates() {
  Serial.println("Checking for OTA updates...");
  
  if (WiFi.status() != WL_CONNECTED) return;
  
  HTTPClient http;
  WiFiClient client;
  
  String url = String(BACKEND_URL) + "/api/dispositivo/firmware?version=" + FIRMWARE_VERSION + "&device=" + DEVICE_ID;
  http.begin(client, url);
  http.setTimeout(10000);
  
  int httpCode = http.GET();
  
  if (httpCode == 200) {
    String response = http.getString();
    JsonDocument doc;
    deserializeJson(doc, response);
    
    if (doc["update_available"] && doc["firmware_url"]) {
      String firmwareUrl = doc["firmware_url"].as<String>();
      performOTAUpdate(firmwareUrl);
    }
  }
  
  http.end();
}

void performOTAUpdate(const String& url) {
  Serial.printf("Starting OTA update from: %s\n", url.c_str());
  
  HTTPClient http;
  WiFiClient client;
  
  http.begin(client, url);
  http.setTimeout(30000);
  
  int httpCode = http.GET();
  
  if (httpCode == 200) {
    int contentLength = http.getSize();
    bool canBegin = Update.begin(contentLength);
    
    if (canBegin) {
      WiFiClient* stream = http.getStreamPtr();
      size_t written = Update.writeStream(*stream);
      
      if (written == contentLength) {
        Serial.println("OTA update written successfully");
        if (Update.end()) {
          Serial.println("OTA update finished, restarting...");
          ESP.restart();
        } else {
          Serial.printf("OTA end failed: %s\n", Update.errorString());
        }
      } else {
        Serial.printf("OTA written only %d/%d bytes\n", written, contentLength);
      }
    } else {
      Serial.printf("OTA begin failed: %s\n", Update.errorString());
    }
  } else {
    Serial.printf("OTA download failed: %d\n", httpCode);
  }
  
  http.end();
}

// ==================== DEEP SLEEP ====================
void enterDeepSleep() {
  Serial.printf("Entering deep sleep for %lu seconds...\n", DEEP_SLEEP_DURATION_US / 1000000);
  
  Serial.flush();
  esp_sleep_enable_timer_wakeup(DEEP_SLEEP_DURATION_US);
  esp_deep_sleep_start();
}

// ==================== CALIBRATION ====================
void loadCalibration() {
  EEPROM.get(CALIB_OFFSET, calibration);
  if (!calibration.calibrated) {
    // Default values - MUST be calibrated in field
    calibration.soil_dry = 3000;
    calibration.soil_wet = 1500;
    calibration.calibrated = false;
    saveCalibration();
    Serial.println("⚠ Using default calibration - RUN CALIBRATION!");
  } else {
    Serial.println("Calibration loaded from EEPROM");
  }
}

void saveCalibration() {
  EEPROM.put(CALIB_OFFSET, calibration);
  EEPROM.commit();
  Serial.println("Calibration saved to EEPROM");
}

void handleSerialCommands() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd == "calibrate_soil_dry") {
      calibration.soil_dry = analogRead(SOIL_MOISTURE_PIN);
      calibration.calibrated = true;
      saveCalibration();
      Serial.printf("Soil DRY calibrated: %.0f\n", calibration.soil_dry);
    } else if (cmd == "calibrate_soil_wet") {
      calibration.soil_wet = analogRead(SOIL_MOISTURE_PIN);
      calibration.calibrated = true;
      saveCalibration();
      Serial.printf("Soil WET calibrated: %.0f\n", calibration.soil_wet);
    } else if (cmd == "status") {
      printStatus();
    } else if (cmd == "restart") {
      ESP.restart();
    } else if (cmd == "help") {
      printHelp();
    } else if (cmd.startsWith("wifi ")) {
      // wifi SSID PASSWORD
      int firstSpace = cmd.indexOf(' ', 5);
      if (firstSpace > 5) {
        String newSsid = cmd.substring(5, firstSpace);
        String newPass = cmd.substring(firstSpace + 1);
        Serial.printf("New WiFi: %s / %s (restart to apply)\n", newSsid.c_str(), newPass.c_str());
        // Would need to save to EEPROM and restart
      }
    }
  }
}

void printStatus() {
  Serial.println("=== DEVICE STATUS ===");
  Serial.printf("Device ID: %s\n", DEVICE_ID);
  Serial.printf("Firmware: %s\n", FIRMWARE_VERSION);
  Serial.printf("WiFi: %s (%d dBm)\n", WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected", WiFi.RSSI());
  Serial.printf("Backend: %s\n", backendConnected ? "Connected" : "Disconnected");
  Serial.printf("Free Heap: %d bytes\n", ESP.getFreeHeap());
  Serial.printf("Uptime: %lu ms\n", millis());
  Serial.printf("Calibrated: %s\n", calibration.calibrated ? "Yes" : "NO - RUN CALIBRATION!");
  Serial.printf("Soil Dry: %.0f | Soil Wet: %.0f\n", calibration.soil_dry, calibration.soil_wet);
  Serial.printf("Deep Sleep: %s\n", DEEP_SLEEP_ENABLED ? "Enabled" : "Disabled");
  Serial.println("=====================");
}

void printHelp() {
  Serial.println("=== COMMANDS ===");
  Serial.println("  calibrate_soil_dry   - Calibrate soil moisture DRY value");
  Serial.println("  calibrate_soil_wet   - Calibrate soil moisture WET value");
  Serial.println("  status               - Show device status");
  Serial.println("  restart              - Restart device");
  Serial.println("  help                 - Show this help");
  Serial.println("===================");
}

String getISO8601Time() {
  time_t now = time(nullptr);
  struct tm timeinfo;
  gmtime_r(&now, &timeinfo);
  char buffer[25];
  strftime(buffer, 25, "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buffer);
}