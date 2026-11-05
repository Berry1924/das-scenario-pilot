/**
 * @file v2v_protocol.cpp
 * @brief ESP-NOW Protocol Driver & Wire Packet Transceiver Implementation
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include "v2v_protocol.h"

V2VProtocol* V2VProtocol::instance = nullptr;

V2VProtocol::V2VProtocol()
    : local_seq_num(0),
      last_peer_seq_num(0),
      packets_sent(0),
      packets_received(0),
      packets_dropped(0),
      crc_errors(0),
      last_rssi(-60),
      new_packet_available(false) {
    instance = this;
}

void V2VProtocol::onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
    /* Send status callback */
}

void V2VProtocol::onDataRecv(const uint8_t *mac, const uint8_t *incomingData, int len) {
    if (!instance || !incomingData) return;

    if (len != sizeof(v2v_packet_t)) {
        return; /* Reject invalid size frames */
    }

    const v2v_packet_t* rx = (const v2v_packet_t*)incomingData;

    /* Validate packet magic, version, and CRC16 */
    v2v_validation_result_t res = v2v_validate_packet(rx, millis());
    if (res == V2V_ERR_CRC_MISMATCH) {
        instance->crc_errors++;
        return;
    }
    if (res != V2V_VALID_OK && res != V2V_ERR_STALE_TIMESTAMP) {
        return;
    }

    /* Validate sequence numbers and track dropped frames */
    uint32_t dropped = 0;
    if (v2v_validate_sequence(rx->seq_num, instance->last_peer_seq_num, &dropped)) {
        instance->packets_dropped += dropped;
        instance->last_peer_seq_num = rx->seq_num;
    }

    /* Store valid packet into buffer */
    memcpy(&instance->rx_buffer, rx, sizeof(v2v_packet_t));
    instance->packets_received++;
    instance->new_packet_available = true;
}

bool V2VProtocol::begin() {
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        return false;
    }

    esp_now_register_send_cb(onDataSent);
    esp_now_register_recv_cb(onDataRecv);

    /* Register peer */
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, PEER_MAC_ADDRESS, 6);
    peerInfo.channel = ESPNOW_WIFI_CHANNEL;
    peerInfo.encrypt = false;

    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        /* Failed to add peer */
    }

    return true;
}

bool V2VProtocol::sendPacket(v2v_priority_t priority,
                            uint16_t hazard_flags,
                            float distance_m,
                            float speed_mps,
                            float accel_mps2,
                            uint32_t current_time_ms) {
    v2v_packet_t pkt;
    pkt.magic = V2V_MAGIC_BYTE;
    pkt.protocol_version = V2V_PROTOCOL_VERSION;
    pkt.priority = (uint8_t)priority;
    pkt.sender_id = LOCAL_NODE_ID;
    pkt.target_id = PEER_NODE_ID;
    pkt.vehicle_type = (uint8_t)LOCAL_VEHICLE_TYPE;
    pkt.hazard_flags = hazard_flags;
    pkt.seq_num = ++local_seq_num;
    pkt.timestamp_ms = current_time_ms;
    pkt.distance_m = distance_m;
    pkt.speed_mps = speed_mps;
    pkt.accel_mps2 = accel_mps2;
    pkt.rssi_dbm = last_rssi;
    pkt.reserved[0] = 0;

    /* Cryptographic signing with CRC16 */
    v2v_sign_packet(&pkt);

    esp_err_t result = esp_now_send(PEER_MAC_ADDRESS, (uint8_t*)&pkt, sizeof(v2v_packet_t));
    if (result == ESP_OK) {
        packets_sent++;
        return true;
    }
    return false;
}

bool V2VProtocol::hasNewPacket() {
    return new_packet_available;
}

v2v_packet_t V2VProtocol::getLatestPacket() {
    new_packet_available = false;
    return rx_buffer;
}
