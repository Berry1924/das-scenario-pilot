/*
 * ============================================================
 * DAAS-V2V VS1 — Sender-Side ACK RTT Firmware (SIH26007)
 * ============================================================
 * OpenCore track implementation. Additive: does not modify
 * the legacy or vehicle-node firmware directories.
 *
 * PURPOSE
 *   Reliable, measurable V2V communication with strict
 *   sender-side ACK RTT measurement:
 *     TX(seq) -> RX -> ACK(seq) -> sender computes RTT
 *   The sender records micros() at TX; the responder returns an
 *   ACK carrying the SAME sequence number; the sender pairs the
 *   ACK by sequence number and computes rtt_us = ack_rx - tx_start.
 *
 *   RTT IS ROUND-TRIP TIME. It is never reported as one-way
 *   latency. Clocks are not synchronized; timestamp_ms is local
 *   monotonic uptime and is used only for freshness audits.
 *
 * TRANSPORT
 *   ESP-NOW 2.4 GHz unicast (802.11b action frames), channel 1.
 *   ESP-NOW is NOT C-V2X or DSRC.
 *
 * WIRE FORMAT
 *   32-byte v2v_packet_t (firmware/common/protocol/v2v_packet.h).
 *
 * SERIAL CSV TELEMETRY (115200 baud, machine-readable)
 *   TX,<seq>,<type>,<time_ms>
 *   RX,<seq>,<type>,<time_ms>
 *   ACK,<seq>,<rtt_us>          (emitted by the responder)
 *   STATE,<mode>                (FULL|V2V_DEGRADED|SENSOR_DEGRADED|BOTH_DEGRADED)
 *   EVENT,<type>[,<detail>]     (e.g. EVENT,EMERGENCY_TX)
 *   Diagnostics use "[TAG] ..." and are excluded from CSV ingestion.
 *
 * ROLES
 *   #define VS1_ROLE_TX 1  -> this node is the periodic sender
 *   #define VS1_ROLE_TX 0  -> this node is the responder
 * ============================================================
 */

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_idf_version.h>
#include "../../common/protocol/v2v_packet.h"
#include "../../common/validation/packet_validator.h"

// ---------------- ROLE & IDENTITY ----------------
#ifndef VS1_ROLE_TX
#define VS1_ROLE_TX 1
#endif

#define FIRMWARE_VERSION    "vs1-ack-rtt-1.0.0"
#define V2V_WIFI_CHANNEL    1

#if VS1_ROLE_TX
static const uint8_t PEER_MAC[6] = {0xC8, 0x2E, 0x18, 0xF4, 0x47, 0x78};  /* responder MAC */
#define LOCAL_SENDER_ID   1
#else
static const uint8_t PEER_MAC[6] = {0x14, 0x08, 0x08, 0xA6, 0x1E, 0xDC};  /* sender MAC */
#define LOCAL_SENDER_ID   2
#endif

// ---------------- PINS (per ADR-005 / node_config.h) ----------------
#define PIN_ULTRASONIC_TRIG      5
#define PIN_ULTRASONIC_ECHO      18
#define PIN_BRAKE_SWITCH         19   /* Active-low push button (INPUT_PULLUP) */
#define PIN_LED_DANGER           4
#define PIN_LED_SAFE             2
#define PIN_BUZZER               13
#define HAS_ULTRASONIC           false  /* VS1 baseline: no sensor required */
#define HAS_BRAKE_SENSOR         true

// ---------------- TIMING ----------------
#define BEACON_INTERVAL_MS       100    /* 10 Hz nominal */
#define BEACON_TYPE              PRIORITY_BEACON
#define RTT_TABLE_SIZE           32     /* pending-TX ring buffer */

// ---------------- STATE ----------------
static uint32_t tx_sequence = 0;
static volatile bool peer_seen = false;
static int8_t  last_rssi = -127;

/* Pending TX table for matched-ACK RTT (seq -> tx_start_us) */
static uint32_t pending_seq[RTT_TABLE_SIZE];
static uint32_t pending_start_us[RTT_TABLE_SIZE];
static uint8_t  pending_head = 0, pending_count = 0;

static volatile bool rx_pending = false;
static v2v_packet_t rx_frame;
static int8_t rx_rssi = -127;

static unsigned long last_tx_ms = 0;
static unsigned long last_state_report_ms = 0;

static uint32_t acks_received = 0;
static uint32_t frames_sent_ok = 0;
static uint32_t frames_sent_fail = 0;

// ---------------- RTT pending table ----------------
static void pending_push(uint32_t seq, uint32_t start_us) {
    if (pending_count >= RTT_TABLE_SIZE) return; /* drop oldest implicitly */
    pending_seq[pending_head] = seq;
    pending_start_us[pending_head] = start_us;
    pending_head = (pending_head + 1) % RTT_TABLE_SIZE;
    pending_count++;
}

static int32_t pending_find(uint32_t seq) {
    for (uint8_t i = 0; i < RTT_TABLE_SIZE; i++) {
        uint8_t idx = (pending_head + RTT_TABLE_SIZE - 1 - i) % RTT_TABLE_SIZE;
        if (i < pending_count && pending_seq[idx] == seq) return idx;
    }
    return -1;
}

static void pending_pop(int32_t idx) {
    if (idx < 0) return;
    pending_seq[idx] = 0;
    if (pending_count > 0) pending_count--;
}

// ---------------- ESP-NOW CALLBACKS ----------------
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
    if (status == ESP_NOW_SEND_SUCCESS) frames_sent_ok++;
    else frames_sent_fail++;
}
void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
    if (len != V2V_PACKET_SIZE) return;
    memcpy(&rx_frame, data, V2V_PACKET_SIZE);
    rx_rssi = info->rx_ctrl->rssi;
    last_rssi = rx_rssi;
    peer_seen = true;
    rx_pending = true;
}
#else
void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
    if (status == ESP_NOW_SEND_SUCCESS) frames_sent_ok++;
    else frames_sent_fail++;
}
void onDataRecv(const uint8_t *mac, const uint8_t *incomingData, int len) {
    if (len != V2V_PACKET_SIZE) return;
    memcpy(&rx_frame, incomingData, V2V_PACKET_SIZE);
    rx_rssi = -127;  /* RSSI not available in legacy callback signature */
    peer_seen = true;
    rx_pending = true;
}
#endif

// ---------------- TRANSMIT ----------------
static void sendFrame(v2v_priority_t prio) {
    v2v_packet_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    pkt.magic = V2V_MAGIC_BYTE;
    pkt.protocol_version = V2V_PROTOCOL_VERSION;
    pkt.priority = prio;
    pkt.sender_id = LOCAL_SENDER_ID;
    pkt.target_id = V2V_BROADCAST_ID;
    pkt.vehicle_type = VEHICLE_TYPE_HAUL_DUMPER_100T;
    pkt.hazard_flags = HAZARD_FLAG_NONE;
    pkt.seq_num = ++tx_sequence;
    pkt.timestamp_ms = millis();
    pkt.distance_m = -1.0f;
    pkt.speed_mps = 0.0f;
    pkt.accel_mps2 = 0.0f;
    pkt.rssi_dbm = last_rssi;
    v2v_sign_packet(&pkt);

#if VS1_ROLE_TX
    uint32_t start_us = micros();
    pending_push(pkt.seq_num, start_us);
#endif

    esp_now_send(PEER_MAC, (uint8_t *)&pkt, sizeof(pkt));

    const char *tname = (prio == PRIORITY_EMERGENCY) ? "EMERGENCY" :
                        (prio == PRIORITY_BEACON)    ? "BEACON" : "CONTROL";
    Serial.printf("TX,%u,%s,%u\n", (unsigned)pkt.seq_num, tname, (unsigned)pkt.timestamp_ms);
    if (prio == PRIORITY_EMERGENCY) {
        Serial.printf("EVENT,EMERGENCY_TX,%u\n", (unsigned)pkt.seq_num);
    }
}

/* Responder ACK: carries the RECEIVED sequence number so the sender can
 * pair it with its pending TX(seq) and compute the round-trip time. */
static void sendAck(uint32_t rx_seq) {
    v2v_packet_t ack;
    memset(&ack, 0, sizeof(ack));
    ack.magic = V2V_MAGIC_BYTE;
    ack.protocol_version = V2V_PROTOCOL_VERSION;
    ack.priority = PRIORITY_CONTROL;
    ack.sender_id = LOCAL_SENDER_ID;
    ack.target_id = V2V_BROADCAST_ID;
    ack.vehicle_type = VEHICLE_TYPE_HAUL_DUMPER_100T;
    ack.hazard_flags = HAZARD_FLAG_NONE;
    ack.seq_num = rx_seq;              /* echo the received sequence */
    ack.timestamp_ms = millis();
    ack.distance_m = -1.0f;
    ack.speed_mps = 0.0f;
    ack.accel_mps2 = 0.0f;
    ack.rssi_dbm = last_rssi;
    v2v_sign_packet(&ack);

    esp_now_send(PEER_MAC, (uint8_t *)&ack, sizeof(ack));
    Serial.printf("TX,%u,ACK,%u\n", (unsigned)rx_seq, (unsigned)ack.timestamp_ms);
}

// ---------------- SETUP ----------------
void setup() {
    Serial.begin(115200);
    delay(500);

    if (HAS_BRAKE_SENSOR) pinMode(PIN_BRAKE_SWITCH, INPUT_PULLUP);
    pinMode(PIN_LED_DANGER, OUTPUT);
    pinMode(PIN_LED_SAFE, OUTPUT);
    pinMode(PIN_BUZZER, OUTPUT);

    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    esp_wifi_set_promiscuous(true);
    esp_wifi_set_channel(V2V_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
    esp_wifi_set_promiscuous(false);

    if (esp_now_init() != ESP_OK) {
        Serial.println("[ERR] esp_now_init failed");
        return;
    }
#if ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5, 0, 0)
    esp_now_register_send_cb(onDataSent);
    esp_now_register_recv_cb(onDataRecv);
#else
    esp_now_register_send_cb((esp_now_send_cb_t)onDataSent);
    esp_now_register_recv_cb((esp_now_recv_cb_t)onDataRecv);
#endif

    esp_now_peer_info_t peer;
    memset(&peer, 0, sizeof(peer));
    memcpy(peer.peer_addr, PEER_MAC, 6);
    peer.channel = V2V_WIFI_CHANNEL;
    peer.encrypt = false;
    esp_now_add_peer(&peer);

    memset(pending_seq, 0, sizeof(pending_seq));
    memset(pending_start_us, 0, sizeof(pending_start_us));

    Serial.printf("[INFO] VS1 ACK-RTT firmware %s role=%s\n", FIRMWARE_VERSION,
                  VS1_ROLE_TX ? "TX" : "RX");
    Serial.printf("[INFO] Own MAC %s\n", WiFi.macAddress().c_str());
    Serial.printf("STATE,%s\n", peer_seen ? "FULL" : "V2V_DEGRADED");
    last_state_report_ms = millis();
}

// ---------------- MAIN LOOP ----------------
void loop() {
    unsigned long now = millis();

    /* 1. Process received frame */
    if (rx_pending) {
        rx_pending = false;
#if VS1_ROLE_TX
        /* Sender: pair ACK(seq) with pending TX to compute RTT.
         * An incoming control frame with our seq_num is the ACK. */
        if (rx_frame.priority == PRIORITY_CONTROL && rx_frame.sender_id != LOCAL_SENDER_ID) {
            int32_t idx = pending_find(rx_frame.seq_num);
            if (idx >= 0) {
                uint32_t rtt_us = micros() - pending_start_us[idx];
                pending_pop(idx);
                acks_received++;
                Serial.printf("ACK,%u,%u\n", (unsigned)rx_frame.seq_num, (unsigned)rtt_us);
            }
        }
#else
        /* Responder: emit RX line and immediately ACK with same seq. */
        Serial.printf("RX,%u,%s,%u\n", (unsigned)rx_frame.seq_num,
                      rx_frame.priority == PRIORITY_EMERGENCY ? "EMERGENCY" : "BEACON",
                      (unsigned)rx_frame.timestamp_ms);
        sendAck(rx_frame.seq_num);
#endif
    }

#if !VS1_ROLE_TX
#endif

    /* 2. Periodic beacon (TX role) / idle (RX role) */
#if VS1_ROLE_TX
    bool brake = HAS_BRAKE_SENSOR ? (digitalRead(PIN_BRAKE_SWITCH) == LOW) : false;
    if (brake) {
        /* Emergency: immediate TX, bypasses the beacon interval */
        sendFrame(PRIORITY_EMERGENCY);
        digitalWrite(PIN_LED_DANGER, HIGH);
        tone(PIN_BUZZER, 2000);
    } else {
        digitalWrite(PIN_LED_DANGER, LOW);
        noTone(PIN_BUZZER);
        if (now - last_tx_ms >= BEACON_INTERVAL_MS) {
            sendFrame(BEACON_TYPE);
            last_tx_ms = now;
        }
    }
#endif

    /* 3. State report (1 Hz) */
    if (now - last_state_report_ms >= 1000) {
        Serial.printf("STATE,%s\n", peer_seen ? "FULL" : "V2V_DEGRADED");
        last_state_report_ms = now;
    }

    /* 4. LED safe indication */
    digitalWrite(PIN_LED_SAFE, peer_seen ? HIGH : LOW);

    delay(1);
}
