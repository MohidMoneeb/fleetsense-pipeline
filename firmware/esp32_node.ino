// Wiring adapted from the Wokwi ESP32 + MPU6050 example project.

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

const char* WIFI_SSID   = "Wokwi-GUEST";
const char* WIFI_PASS   = "";
const char* MQTT_BROKER = "test.mosquitto.org";
const int   MQTT_PORT   = 1883;
const char* NODE_ID     = "esp32-node-01";
const char* TOPIC       = "fleet/esp32-node-01/telemetry";

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
Adafruit_MPU6050 mpu;

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(200); Serial.print("."); }
  Serial.println("\nWiFi connected");
}

void connectMQTT() {
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  while (!mqtt.connected()) {
    String cid = String(NODE_ID) + "-" + String(random(0xffff), HEX);
    if (mqtt.connect(cid.c_str())) {
      Serial.println("MQTT connected");
    } else {
      Serial.print("MQTT failed rc="); Serial.println(mqtt.state());
      delay(1000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("BOOT OK");
  if (!mpu.begin()) { Serial.println("MPU6050 NOT FOUND"); }
  else { Serial.println("MPU6050 ready"); }
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  connectWiFi();
  connectMQTT();
}

void loop() {
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  char payload[200];
  snprintf(payload, sizeof(payload),
    "{\"vehicle_id\":\"%s\",\"accel_x\":%.2f,\"accel_y\":%.2f,\"accel_z\":%.2f}",
    NODE_ID, a.acceleration.x, a.acceleration.y, a.acceleration.z);

  mqtt.publish(TOPIC, payload);
  Serial.println(payload);
  delay(1000);
}