/**
 * @file v2v_protocol.h
 * @brief ESP-NOW Protocol Driver & Wire Packet Transceiver Subsystem
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef V2V_PROTOCOL_H
#define V2V_PROTOCOL_H

#include <Arduino.h>
#include <esp_now.h>
#include <WiFi.h>
#include "../include/node_config.h"
#include "../../common/protocol/v2v_packet.h"
#include "../../common/validation/packet_validator.h"

class V2VProtocol {
public:
    V2VProtocol();
    bool begin();

    bool sendPacket(v2v_priority_t priority,
                    uint16_t hazard_flags,
                    float distance_m,
                    float speed_mps,
                    float accel_mps2,
                    uint32_t current_time_ms);

    bool hasNewPacket();
    v2v_packet_t getLatestPacket();

    uint32_t getPacketsSent() const { return packets_sent; }
    uint32_t getPacketsReceived() const { return packets_received; }
    uint32_t getPacketsDropped() const { return packets_dropped; }
    uint32_t getCrcErrors() const { return crc_errors; }
    int8_t getLastRssi() const { return last_rssi; }

    static void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status);
    static void onDataRecv(const uint8_t *mac, const uint8_t *incomingData, int len);

private:
    static V2VProtocol* instance;

    uint32_t local_seq_num;
    uint32_t last_peer_seq_num;
    uint32_t packets_sent;
    uint32_t packets_received;
    uint32_t packets_dropped;
    uint32_t crc_errors;
    int8_t   last_rssi;

    v2v_packet_t rx_buffer;
    volatile bool new_packet_available;
};

#endif /* V2V_PROTOCOL_H */
