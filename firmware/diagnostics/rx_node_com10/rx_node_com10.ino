/**
 * @file rx_node_com10.ino
 * @brief DAAS-V2V H3 DIAGNOSTIC firmware — Vehicle 2 / RX node (Windows COM9)
 *
 * Purpose: ESP-NOW reception of TX beacons -> full packet validation
 *   (magic, version, CRC16, kinematic bounds, duplicate-sequence rejection)
 *   -> APPLICATION-LEVEL ACK back to sender -> OLED status -> LED indication
 *   -> structured serial telemetry for laptop capture.
 *
 * Board target : ESP32 Dev Module (esp32 core 3.3.11, installed on this PC)
 * Serial       : 115200 baud, JSON lines at 10 Hz
 * OLED         : SSD1306 128x64, I2C 0x3C, SDA=21 SCL=22 (Adafruit_SSD1306 — installed)
 * LEDs         : DANGER=4 (red), SAFE=2 (green/onboard) — per node_config.h
 * Buzzer       : GPIO13 (active piezo, digitalWrite per production hmi.cpp)
 *                *** DISABLED BY DEFAULT (BUZZER_ENABLE 0) until wiring verified ***
 *
 * Validation mirrors firmware/common/validation/packet_validator.h.
 * Staleness check is run with current_time_ms = 0 (skipped): sender and receiver
 * uptime clocks are independent on the bench (documented cross-clock caveat, H2B).
 * Duplicate-sequence rejection mirrors v2v_validate_sequence().
 *
 * The ACK carries seq_num = acknowledged TX sequence and is matched by the TX
 * node to measure application-level ACK RTT.
 *
 * NO API KEYS. No cloud. Muse Spark is outside this path. Bench use only.
 */

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <esp_now.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "v2v_packet.h"

/* ---------------- Node identity ---------------- */
static const uint8_t RX_NODE_ID = 2;
static const uint8_t TX_NODE_ID = 1;
static const uint8_t ESPNOW_WIFI_CHANNEL = 1; /* node_config.h: ESPNOW_WIFI_CHANNEL */

/* ---------------- Pins (per node_config.h / ADR-005) ---------------- */
static const int PIN_LED_DANGER  = 4;   /* red */
static const int PIN_LED_SAFE    = 2;   /* green (on-board LED) */
static const int PIN_BUZZER      = 13;  /* active piezo */
static const int PIN_OLED_SDA    = 21;
static const int PIN_OLED_SCL    = 22;

/* Display configuration (node_config.h values, ADR-005) */
static const uint8_t SCREEN_WIDTH       = 128;
static const uint8_t SCREEN_HEIGHT      = 64;
static const int8_t  OLED_RESET_PIN     = -1;
static const uint8_t SCREEN_I2C_ADDRESS = 0x3C;

/* ---------------- Safety gate ---------------- */
/* Buzzer stays OFF until wiring + driver verified on the bench (H3 directive).
 * Set to 1 ONLY after the piezo polarity/current-limit has been confirmed. */
#define BUZZER_ENABLE 0

/* ---------------- Display (mirrors production hmi.cpp) ---------------- */
static Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET_PIN);
static bool oled_ok = false;

/* ---------------- Risk thresholds (mirror risk_engine.cpp mapping) -------- */
static const float THRESHOLD_DIST_CRITICAL_M = 4.0f;

/* ---------------- State ---------------- */
static uint32_t accepted_cnt   = 0;
static uint32_t duplicate_cnt  = 0;
static uint32_t crc_err_cnt    = 0;
static uint32_t oob_cnt        = 0;
static uint32_t bad_magic_cnt  = 0;
static uint32_t bad_ver_cnt    = 0;
static uint32_t size_err_cnt   = 0;
static uint32_t drop_est_cnt   = 0;
static uint32_t ack_fail_cnt   = 0;
static uint32_t last_seq       = 0;
static int8_t   last_rssi      = 0;
static float    last_dist_m    = -1.0f;
static bool     peer_critical  = false;
static bool     have_packet    = false;

/* Deferred work: recv callback only stores, loop sends ACK */
static volatile bool     ack_pending  = false;
static uint8_t           ack_peer[6]  = {0};
static v2v_packet_t      ack_frame;
static volatile uint32_t ack_target_seq = 0;

static uint32_t last_telemetry_ms = 0;

/* ---------------- Validation (identical math to production) --------------- */
/* v2v_compute_crc16 / v2v_validate_packet / v2v_validate_sequence are provided
 * by the bundled v2v_packet.h (copy of firmware/common/protocol/v2v_packet.h
 * + validator inlines). Staleness is invoked with current_time_ms = 0. */

/* ---------------- ESP-NOW callbacks (esp32 core 3.x signature) ----------- */
static void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  (void)info;
  if (status != ESP_NOW_SEND_SUCCESS) {
    ack_fail_cnt++;
  }
}

static void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (!data || len != (int)sizeof(v2v_packet_t)) {
    size_err_cnt++;
    return;
  }

  v2v_packet_t rx;
  memcpy(&rx, data, sizeof(rx));

  v2v_validation_result_t res = v2v_validate_packet(&rx, 0); /* 0 => skip staleness (cross-clock) */
  switch (res) {
    case V2V_ERR_CRC_MISMATCH: crc_err_cnt++;   return;
    case V2V_ERR_BAD_MAGIC:    bad_magic_cnt++; return;
    case V2V_ERR_UNSUPPORTED_VERSION: bad_ver_cnt++; return;
    case V2V_ERR_OUT_OF_BOUNDS: oob_cnt++;      return;
    default: break;
  }

  /* Sequence freshness + duplicate/replay rejection */
  uint32_t dropped = 0;
  if (!v2v_validate_sequence(rx.seq_num, last_seq, &dropped)) {
    duplicate_cnt++;
    return;
  }
  drop_est_cnt += dropped;
  last_seq = rx.seq_num;
  accepted_cnt++;

  last_rssi     = (int8_t)(info->rx_ctrl ? info->rx_ctrl->rssi : 0);
  last_dist_m   = rx.distance_m;
  have_packet   = true;
  /* Production risk mapping (risk_engine.cpp:26-28): peer BRAKE_ACTIVE => CRITICAL */
  peer_critical = ((rx.hazard_flags & HAZARD_FLAG_BRAKE_ACTIVE) != 0)
                  || (rx.distance_m > 0.0f && rx.distance_m < THRESHOLD_DIST_CRITICAL_M);

  /* Queue app-level ACK for the loop (never add peer / long work in callback) */
  memcpy(ack_peer, info->src_addr, 6);
  ack_frame = rx;                       /* reuse received frame as ACK carrier */
  ack_frame.sender_id    = RX_NODE_ID;
  ack_frame.target_id    = TX_NODE_ID;
  ack_frame.priority     = PRIORITY_CONTROL;
  ack_frame.seq_num      = rx.seq_num;  /* ACKed sequence */
  ack_frame.distance_m   = 1.0f;        /* ACK-ok marker */
  ack_frame.hazard_flags = HAZARD_FLAG_NONE;
  ack_frame.crc16        = 0;
  ack_frame.crc16 = v2v_compute_crc16((const uint8_t *)&ack_frame, V2V_CRC_OFFSET);
  ack_pending = true;
  ack_target_seq = rx.seq_num;
}

/* ---------------- Setup ---------------- */
void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(PIN_LED_DANGER, OUTPUT);
  pinMode(PIN_LED_SAFE, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_LED_DANGER, LOW);
  digitalWrite(PIN_LED_SAFE, HIGH);
  digitalWrite(PIN_BUZZER, LOW);

  Wire.begin(PIN_OLED_SDA, PIN_OLED_SCL);
  oled_ok = display.begin(SSD1306_SWITCHCAPVCC, SCREEN_I2C_ADDRESS);
  if (oled_ok) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(0, 10);
    display.println(F("  DAAS-V2V RX DIAG"));
    display.setCursor(0, 25);
    display.println(F("  BOOT OK"));
    display.display();
  }

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  if (esp_now_init() != ESP_OK) {
    Serial.println(F("{\"fatal\":\"esp_now_init failed\"}"));
    while (true) delay(1000);
  }
  esp_now_register_send_cb(onDataSent);
  esp_now_register_recv_cb(onDataRecv);

  /* Boot banner: MAC discovery for the TX node's PEER_MAC + collector keying */
  Serial.println();
  Serial.print(F("{\"boot\":\"rx_node_com10\",\"proto\":"));
  Serial.print(V2V_PROTOCOL_VERSION);
  Serial.print(F(",\"node\":"));
  Serial.print(RX_NODE_ID);
  Serial.print(F(",\"my_mac\":\""));
  Serial.print(WiFi.macAddress());
  Serial.print(F("\",\"oled\":"));
  Serial.print(oled_ok ? 1 : 0);
  Serial.println(F(",\"ch\":1}"));
}

/* ---------------- Helpers ---------------- */
static void sendAckIfPending() {
  if (!ack_pending) return;
  ack_pending = false;

  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, ack_peer, 6);
  peer.channel = ESPNOW_WIFI_CHANNEL;
  peer.ifidx   = WIFI_IF_STA;
  peer.encrypt = false;
  if (esp_now_add_peer(&peer) != ESP_OK && esp_now_mod_peer(&peer) != ESP_OK) {
    ack_fail_cnt++;
    return;
  }
  if (esp_now_send(ack_peer, (uint8_t *)&ack_frame, sizeof(ack_frame)) != ESP_OK) {
    ack_fail_cnt++;
  }
  (void)ack_target_seq;
}

static void updateOutputs() {
  if (!have_packet) {
    digitalWrite(PIN_LED_SAFE, HIGH);   /* no data yet: idle-safe */
    digitalWrite(PIN_LED_DANGER, LOW);
    return;
  }
  if (peer_critical) {
    digitalWrite(PIN_LED_DANGER, HIGH);
    digitalWrite(PIN_LED_SAFE, LOW);
#if BUZZER_ENABLE
    digitalWrite(PIN_BUZZER, HIGH);
#endif
  } else {
    digitalWrite(PIN_LED_DANGER, LOW);
    digitalWrite(PIN_LED_SAFE, HIGH);
#if BUZZER_ENABLE
    digitalWrite(PIN_BUZZER, LOW);
#endif
  }
}

static void updateOled() {
  if (!oled_ok) return;
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println(F("DAAS-V2V RX DIAG"));
  display.setCursor(0, 14);
  if (have_packet) {
    display.print(F("dist: "));
    display.print(last_dist_m, 2);
    display.println(F(" m"));
    display.setCursor(0, 26);
    display.print(F("seq: "));
    display.println(last_seq);
    display.setCursor(0, 38);
    display.print(F("rssi: "));
    display.println(last_rssi);
  } else {
    display.println(F("waiting for TX..."));
  }
  display.setCursor(0, 52);
  display.print(F("ok:"));
  display.print(accepted_cnt);
  display.print(F(" dup:"));
  display.print(duplicate_cnt);
  display.print(F(" crc:"));
  display.print(crc_err_cnt);
  display.display();
}

/* ---------------- Loop ---------------- */
void loop() {
  uint32_t now = millis();

  sendAckIfPending();
  updateOutputs();

  static uint32_t last_oled_ms = 0;
  if (now - last_oled_ms >= 250) {   /* 4 Hz display refresh */
    last_oled_ms = now;
    updateOled();
  }

  if (now - last_telemetry_ms >= 100) {  /* 10 Hz JSON */
    last_telemetry_ms = now;
    Serial.print(F("{\"uptime\":"));
    Serial.print(now);
    Serial.print(F(",\"node\":"));
    Serial.print(RX_NODE_ID);
    Serial.print(F(",\"role\":\"RX\",\"last_seq\":"));
    Serial.print(last_seq);
    Serial.print(F(",\"dist\":"));
    Serial.print(last_dist_m, 2);
    Serial.print(F(",\"critical\":"));
    Serial.print(peer_critical ? 1 : 0);
    Serial.print(F(",\"acc_cnt\":"));
    Serial.print(accepted_cnt);
    Serial.print(F(",\"dup_cnt\":"));
    Serial.print(duplicate_cnt);
    Serial.print(F(",\"drop_est\":"));
    Serial.print(drop_est_cnt);
    Serial.print(F(",\"crc_err\":"));
    Serial.print(crc_err_cnt);
    Serial.print(F(",\"oob_cnt\":"));
    Serial.print(oob_cnt);
    Serial.print(F(",\"bad_magic\":"));
    Serial.print(bad_magic_cnt);
    Serial.print(F(",\"bad_ver\":"));
    Serial.print(bad_ver_cnt);
    Serial.print(F(",\"size_err\":"));
    Serial.print(size_err_cnt);
    Serial.print(F(",\"ack_fail\":"));
    Serial.print(ack_fail_cnt);
    Serial.print(F(",\"rssi\":"));
    Serial.print(last_rssi);
    Serial.print(F(",\"oled\":"));
    Serial.print(oled_ok ? 1 : 0);
    Serial.println(F("}"));
  }
}
