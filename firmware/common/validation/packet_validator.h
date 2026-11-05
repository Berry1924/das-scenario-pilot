/**
 * @file packet_validator.h
 * @brief Wire-Protocol Packet Validation & Integrity Checks
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef PACKET_VALIDATOR_H
#define PACKET_VALIDATOR_H

#include "../protocol/v2v_packet.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Maximum acceptable message age before marking frame as stale (500 ms) */
#define V2V_MAX_MESSAGE_AGE_MS 500

/* Validation Result Codes */
typedef enum {
    V2V_VALID_OK               = 0x00,
    V2V_ERR_NULL_POINTER       = 0x01,
    V2V_ERR_BAD_MAGIC          = 0x02,
    V2V_ERR_UNSUPPORTED_VERSION= 0x03,
    V2V_ERR_CRC_MISMATCH       = 0x04,
    V2V_ERR_STALE_TIMESTAMP    = 0x05,
    V2V_ERR_OUT_OF_BOUNDS      = 0x06,
    V2V_ERR_DUPLICATE_SEQUENCE = 0x07
} v2v_validation_result_t;

/**
 * @brief Computes standard CRC16-CCITT (polynomial 0x1021, init 0xFFFF).
 */
static inline uint16_t v2v_compute_crc16(const uint8_t* data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (uint8_t bit = 0; bit < 8; bit++) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc = crc << 1;
            }
        }
    }
    return crc;
}

/**
 * @brief Signs a packet by computing CRC16 across the payload and storing it in packet->crc16.
 */
static inline void v2v_sign_packet(v2v_packet_t* packet) {
    if (!packet) return;
    packet->crc16 = v2v_compute_crc16((const uint8_t*)packet, V2V_CRC_OFFSET);
}

/**
 * @brief Performs strict structural and cryptographic integrity check on an incoming frame.
 */
static inline v2v_validation_result_t v2v_validate_packet(const v2v_packet_t* packet, uint32_t current_time_ms) {
    if (!packet) {
        return V2V_ERR_NULL_POINTER;
    }

    /* 1. Magic Byte Check */
    if (packet->magic != V2V_MAGIC_BYTE) {
        return V2V_ERR_BAD_MAGIC;
    }

    /* 2. Protocol Version Check */
    if (packet->protocol_version != V2V_PROTOCOL_VERSION) {
        return V2V_ERR_UNSUPPORTED_VERSION;
    }

    /* 3. CRC16 Checksum Verification */
    uint16_t calculated_crc = v2v_compute_crc16((const uint8_t*)packet, V2V_CRC_OFFSET);
    if (calculated_crc != packet->crc16) {
        return V2V_ERR_CRC_MISMATCH;
    }

    /* 4. Timestamp Freshness Check (if current_time_ms is provided) */
    if (current_time_ms > 0 && current_time_ms >= packet->timestamp_ms) {
        uint32_t age_ms = current_time_ms - packet->timestamp_ms;
        if (age_ms > V2V_MAX_MESSAGE_AGE_MS) {
            return V2V_ERR_STALE_TIMESTAMP;
        }
    }

    /* 5. Physical Kinematic Bounds Validation */
    if (packet->distance_m < 0.0f || packet->distance_m > 5000.0f) {
        return V2V_ERR_OUT_OF_BOUNDS;
    }
    if (packet->speed_mps < -30.0f || packet->speed_mps > 70.0f) {
        return V2V_ERR_OUT_OF_BOUNDS;
    }
    if (packet->accel_mps2 < -25.0f || packet->accel_mps2 > 20.0f) {
        return V2V_ERR_OUT_OF_BOUNDS;
    }

    return V2V_VALID_OK;
}

/**
 * @brief Evaluates monotonic sequence progression to detect dropped packets or replays.
 * @param new_seq Sequence number of received packet.
 * @param last_seq Sequence number of previous valid packet received from this peer.
 * @param[out] dropped_count Output pointer to store estimated dropped packet count.
 * @return true if sequence is valid (strictly greater); false if duplicate or replayed.
 */
static inline bool v2v_validate_sequence(uint32_t new_seq, uint32_t last_seq, uint32_t* dropped_count) {
    if (last_seq == 0 && new_seq > 0) {
        /* Initial sync packet */
        if (dropped_count) *dropped_count = 0;
        return true;
    }
    
    if (new_seq > last_seq) {
        if (dropped_count) {
            *dropped_count = (new_seq - last_seq) - 1;
        }
        return true;
    }
    
    /* Replayed or duplicate sequence */
    if (dropped_count) *dropped_count = 0;
    return false;
}

#ifdef __cplusplus
}
#endif

#endif /* PACKET_VALIDATOR_H */
