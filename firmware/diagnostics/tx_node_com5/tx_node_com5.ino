/**
 * @file tx_node_com5.ino
 * @brief DAAS-V2V H3 DIAGNOSTIC firmware — Vehicle 1 / TX node (Windows COM5)
 *
 * Purpose: repeatable bench acceptance for the H3 chain:
 *   HC-SR04 measurement -> ESP-NOW TX -> (RX validates + ACKs) -> app-level ACK
 *   -> structured serial telemetry for laptop capture.
 *
 * Board target : ESP32 Dev Module (esp32 core 3.3.11, installed on this PC)
 * Serial       : 115200 baud, JSON lines at 10 Hz
 * Sensor pins  : TRIG=5, ECHO=18 (from firmware/vehicle-node/include/node_config.h, ADR-005)
 * Brake switch : GPIO19 active-low (mirrors production)
 *
 * Wire format  : firmware/common/protocol/v2v_packet.h (32-byte packed frame, CRC16-CCITT)
 * ESP-NOW      : STA mode, channel 1, no encryption (mirrors production v2v_protocol.cpp)
 *
 * Application-level ACK (NOT in production firmware — production discards MAC-layer
 * status, v2v_protocol.cpp:23-25): RX replies with a v2v_packet_t where
 *   sender_id = 2 (RX), target_id = 1 (TX), priority = PRIORITY_CONTROL,
 *   seq_num   = acknowledged TX sequence, distance_m = 1.0 (ACK marker).
 * This sketch matches the ACK to its pending-send ring and reports ack_rtt_ms.
 *
 * === YOU MUST EDIT THIS FILE ONCE ===
 * Set PEER_MAC below to the MAC printed by the RX node (rx_node_com10) boot banner.
 *
 * NO API KEYS. No cloud. Muse Spark is outside this path. Bench use only.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include "v2v_packet.h"

/* ---------------- Node identity (EDIT PEER_MAC once) ---------------- */
static const uint8_t PEER_MAC[6] = { 0x88, 0x57, 0x21, 0xAD, 0x91, 0x80 }; /* <- RX node MAC (from rx boot banner) */
static const uint8_t TX_NODE_ID  = 1;
static const uint8_t RX_NODE_ID  = 2;
static const uint8_t ESPNOW_WIFI_CHANNEL = 1; /* node_config.h: ESPNOW_WIFI_CHANNEL */

/* ---------------- Pins (per node_config.h / ADR-005) ---------------- */
static const int PIN_ULTRASONIC_TRIG = 5;
static const int PIN_ULTRASONIC_ECHO = 18;
static const int PIN_BRAKE_SWITCH    = 19;   /* active-low, internal pull-up */

/* ---------------- Timing (mirrors production) ---------------- */
static const uint32_t SENSOR_POLL_INTERVAL_MS  = 50;   /* 20 Hz ping */
static const uint32_t TELEMETRY_INTERVAL_MS    = 100;  /* 10 Hz JSON */
static const uint32_t TX_INTERVAL_MS           = 100;  /* 10 Hz nominal beacon */
static const uint32_t ACK_TIMEOUT_MS           = 750;  /* pending-entry expiry */

/* ---------------- State ---------------- */
static uint32_t seq_counter      = 0;
static uint32_t packets_sent     = 0;
static uint32_t send_fail_cnt    = 0;
static uint32_t ack_ok_cnt       = 0;
static uint32_t ack_stale_cnt    = 0;
static int32_t  last_ack_rtt_ms  = -1;
static float    last_distance_m  = 50.0f;
static bool     sensor_fault     = false;
static bool     brake_active     = false;
static uint32_t last_send_ms     = 0;
static uint32_t last_telemetry_ms= 0;

/* Pending-send ring for ACK matching: seq -> send time */
static const uint8_t PENDING_N = 8;
static uint32_t pending_seq[PENDING_N];
static uint32_t pending_ms[PENDING_N];
static uint8_t  pending_head = 0;

/* ---------------- Packet helpers (identical to production common code) --- */
static void sign_packet(v2v_packet_t *p) {
  p->crc16 = v2v_compute_crc16((const uint8_t *)p, V2V_CRC_OFFSET);
}

/* ---------------- ESP-NOW callbacks (esp32 core 3.x signature) ----------- */
static void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  (void)info;
  if (status != ESP_NOW_SEND_SUCCESS) {
    send_fail_cnt++;
  }
}

static void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (!data || len != (int)sizeof(v2v_packet_t)) return;

  v2v_packet_t ack;
  memcpy(&ack, data, sizeof(ack));

  /* Accept only a well-formed ACK from our RX node addressed to us */
  if (ack.magic != V2V_MAGIC_BYTE || ack.protocol_version != V2V_PROTOCOL_VERSION) return;
  if (ack.sender_id != RX_NODE_ID || ack.target_id != TX_NODE_ID) return;
  if (ack.priority != PRIORITY_CONTROL) return;
  if (v2v_compute_crc16((const uint8_t *)&ack, V2V_CRC_OFFSET) != ack.crc16) return;

  /* Match against pending ring */
  for (uint8_t i = 0; i < PENDING_N; i++) {
    if (pending_seq[i] == ack.seq_num && pending_ms[i] != 0) {
      last_ack_rtt_ms = (int32_t)(millis() - pending_ms[i]);
      pending_ms[i] = 0;                 /* consume entry */
      pending_seq[i] = 0;
      ack_ok_cnt++;
      return;
    }
  }
  ack_stale_cnt++; /* ACK for a seq we no longer track */
}

/* ---------------- Setup ---------------- */
void setup() {
  Serial.begin(115200);
  delay(200);

  pinMode(PIN_ULTRASONIC_TRIG, OUTPUT);
  pinMode(PIN_ULTRASONIC_ECHO, INPUT);
  pinMode(PIN_BRAKE_SWITCH, INPUT_PULLUP);
  digitalWrite(PIN_ULTRASONIC_TRIG, LOW);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  if (esp_now_init() != ESP_OK) {
    Serial.println(F("{\"fatal\":\"esp_now_init failed\"}"));
    while (true) delay(1000);
  }
  esp_now_register_send_cb(onDataSent);
  esp_now_register_recv_cb(onDataRecv);

  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, PEER_MAC, 6);
  peer.channel = ESPNOW_WIFI_CHANNEL;
  peer.ifidx   = WIFI_IF_STA;
  peer.encrypt = false;
  if (esp_now_add_peer(&peer) != ESP_OK) {
    Serial.println(F("{\"fatal\":\"esp_now_add_peer failed\"}"));
    while (true) delay(1000);
  }

  memset(pending_seq, 0, sizeof(pending_seq));
  memset(pending_ms,  0, sizeof(pending_ms));

  /* Boot banner: discovery + identity (telemetry collector keys on this) */
  Serial.println();
  Serial.print(F("{\"boot\":\"tx_node_com5\",\"proto\":"));
  Serial.print(V2V_PROTOCOL_VERSION);
  Serial.print(F(",\"node\":"));
  Serial.print(TX_NODE_ID);
  Serial.print(F(",\"my_mac\":\""));
  Serial.print(WiFi.macAddress());
  Serial.print(F("\",\"peer_mac\":\""));
  char b[18];
  snprintf(b, sizeof(b), "%02X:%02X:%02X:%02X:%02X:%02X",
           PEER_MAC[0], PEER_MAC[1], PEER_MAC[2], PEER_MAC[3], PEER_MAC[4], PEER_MAC[5]);
  Serial.print(b);
  Serial.println(F("\",\"ch\":1}"));
}

/* ---------------- Sensor (mirrors sensor_manager.cpp:31-46) -------------- */
static float readUltrasonicRaw() {
  digitalWrite(PIN_ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_ULTRASONIC_TRIG, LOW);

  unsigned long duration_us = pulseIn(PIN_ULTRASONIC_ECHO, HIGH, 30000);
  if (duration_us == 0) {
    return 50.0f; /* production sentinel: open space / timeout */
  }
  float distance_cm = (duration_us * 0.0343f) / 2.0f;
  return distance_cm / 100.0f;
}

/* ---------------- Loop ---------------- */
void loop() {
  uint32_t now = millis();

  /* Sensor at 20 Hz */
  static uint32_t last_sensor_ms = 0;
  if (now - last_sensor_ms >= SENSOR_POLL_INTERVAL_MS) {
    last_sensor_ms = now;
    float d = readUltrasonicRaw();
    sensor_fault = (d >= 50.0f);
    last_distance_m = d;
    brake_active = (digitalRead(PIN_BRAKE_SWITCH) == LOW);
  }

  /* Beacon at 10 Hz */
  if (now - last_send_ms >= TX_INTERVAL_MS) {
    last_send_ms = now;
    seq_counter++;

    v2v_packet_t pkt = {};
    pkt.magic            = V2V_MAGIC_BYTE;
    pkt.protocol_version = V2V_PROTOCOL_VERSION;
    pkt.priority         = brake_active ? PRIORITY_EMERGENCY : PRIORITY_BEACON;
    pkt.sender_id        = TX_NODE_ID;
    pkt.target_id        = V2V_BROADCAST_ID;
    pkt.vehicle_type     = VEHICLE_TYPE_HAUL_DUMPER_100T;
    pkt.hazard_flags     = (brake_active ? HAZARD_FLAG_BRAKE_ACTIVE : HAZARD_FLAG_NONE)
                           | (sensor_fault ? HAZARD_FLAG_SENSOR_FAULT : HAZARD_FLAG_NONE);
    pkt.seq_num          = seq_counter;
    pkt.timestamp_ms     = now;
    pkt.distance_m       = last_distance_m;
    pkt.speed_mps        = 0.0f;   /* no wheel odometry on bench */
    pkt.accel_mps2       = 0.0f;
    pkt.rssi_dbm         = 0;
    pkt.reserved[0]      = 0;
    sign_packet(&pkt);

    esp_err_t r = esp_now_send(PEER_MAC, (uint8_t *)&pkt, sizeof(pkt));
    if (r == ESP_OK) {
      packets_sent++;
      pending_seq[pending_head] = seq_counter;
      pending_ms[pending_head]  = now;
      pending_head = (pending_head + 1) % PENDING_N;
    } else {
      send_fail_cnt++;
    }
  }

  /* Telemetry at 10 Hz */
  if (now - last_telemetry_ms >= TELEMETRY_INTERVAL_MS) {
    last_telemetry_ms = now;
    Serial.print(F("{\"uptime\":"));
    Serial.print(now);
    Serial.print(F(",\"node\":"));
    Serial.print(TX_NODE_ID);
    Serial.print(F(",\"role\":\"TX\",\"seq\":"));
    Serial.print(seq_counter);
    Serial.print(F(",\"dist\":"));
    Serial.print(last_distance_m, 2);
    Serial.print(F(",\"brake\":"));
    Serial.print(brake_active ? 1 : 0);
    Serial.print(F(",\"sensor_fault\":"));
    Serial.print(sensor_fault ? 1 : 0);
    Serial.print(F(",\"tx_cnt\":"));
    Serial.print(packets_sent);
    Serial.print(F(",\"send_fail\":"));
    Serial.print(send_fail_cnt);
    Serial.print(F(",\"ack_cnt\":"));
    Serial.print(ack_ok_cnt);
    Serial.print(F(",\"ack_stale\":"));
    Serial.print(ack_stale_cnt);
    Serial.print(F(",\"ack_rtt_ms\":"));
    Serial.print(last_ack_rtt_ms);
    Serial.println(F("}"));
  }
}
