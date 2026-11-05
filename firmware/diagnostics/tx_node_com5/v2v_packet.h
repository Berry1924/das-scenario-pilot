/**
 * @file v2v_packet.h
 * @brief Canonical V2V Wire Protocol Packet Definition for DAAS-V2V / SIH26007
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 * 
 * Wire-format structure definition with strict alignment and CRC16 checksum.
 * Designed for over-the-air transmission via ESP-NOW, C-V2X (PC5), or serial bridge.
 */

#ifndef V2V_PACKET_H
#define V2V_PACKET_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Protocol Synchronization Constants */
#define V2V_MAGIC_BYTE         0xD4
#define V2V_PROTOCOL_VERSION   0x02
#define V2V_BROADCAST_ID       0xFF

/* Priority Level Enumeration */
typedef enum {
    PRIORITY_EMERGENCY = 0x00, /* Life-critical: Hard Brake, Imminent Collision (Zero-Queue Delay) */
    PRIORITY_CONTROL   = 0x01, /* Control Frame: Lane change, yield request, berm breach alert */
    PRIORITY_WARNING   = 0x02, /* Advisory: Blind curve presence, weather degradation warning */
    PRIORITY_BEACON    = 0x03  /* Routine: Periodic kinematic status (rate-adaptive by ML) */
} v2v_priority_t;

/* Mining Vehicle Classifications */
typedef enum {
    VEHICLE_TYPE_UNKNOWN        = 0x00,
    VEHICLE_TYPE_HAUL_DUMPER_85T= 0x01,
    VEHICLE_TYPE_HAUL_DUMPER_100T=0x02,
    VEHICLE_TYPE_HAUL_DUMPER_240T=0x03,
    VEHICLE_TYPE_SHOVEL_EXCAVATOR=0x04,
    VEHICLE_TYPE_WATER_BOWSER   = 0x05,
    VEHICLE_TYPE_MOTOR_GRADER   = 0x06,
    VEHICLE_TYPE_LIGHT_VEHICLE  = 0x07,
    VEHICLE_TYPE_ROADSIDE_UNIT  = 0x08
} v2v_vehicle_type_t;

/* Hazard Bitmask Flags */
#define HAZARD_FLAG_NONE               0x0000
#define HAZARD_FLAG_BRAKE_ACTIVE       (1 << 0) /* Operator actively depressing emergency brake */
#define HAZARD_FLAG_IMMINENT_COLLISION (1 << 1) /* Local risk engine detected TTC < critical threshold */
#define HAZARD_FLAG_STALLED_VEHICLE    (1 << 2) /* Vehicle disabled / engine stall in haul road */
#define HAZARD_FLAG_LOW_VISIBILITY_FOG (1 << 3) /* Extreme fog / dust cloud reported by driver or sensor */
#define HAZARD_FLAG_BERM_PROXIMITY     (1 << 4) /* Vehicle dangerously close to bench crest or berm */
#define HAZARD_FLAG_SENSOR_FAULT       (1 << 5) /* Local ranging sensor timeout or hardware failure */

/* Risk Level Assessment Classification */
typedef enum {
    RISK_LEVEL_SAFE     = 0, /* Green: Distance > 15m, TTC > 5.0s, no peer hazard */
    RISK_LEVEL_CAUTION  = 1, /* Yellow: Distance 8-15m, TTC 3.0-5.0s */
    RISK_LEVEL_WARNING  = 2, /* Orange: Distance 4-8m, TTC 1.5-3.0s */
    RISK_LEVEL_CRITICAL = 3  /* Red: Distance < 4m, TTC < 1.5s OR Emergency Brake flag set */
} v2v_risk_level_t;

/**
 * @brief Packed Wire Format for V2V Frame (Total 32 Bytes)
 * Aligned to 1-byte boundary to ensure binary equivalence across platforms.
 */
#pragma pack(push, 1)
typedef struct {
    uint8_t  magic;             /* 0x00: 0xD4 protocol sync byte */
    uint8_t  protocol_version;  /* 0x01: 0x02 current wire schema */
    uint8_t  priority;          /* 0x02: v2v_priority_t (0=Emergency to 3=Routine) */
    uint8_t  sender_id;         /* 0x03: Unique Vehicle ID (1-254) */
    uint8_t  target_id;         /* 0x04: Target ID or 0xFF for broadcast */
    uint8_t  vehicle_type;      /* 0x05: v2v_vehicle_type_t */
    uint16_t hazard_flags;      /* 0x06: Bitmask of active hazards */
    uint32_t seq_num;           /* 0x08: Monotonic sequence counter per sender */
    uint32_t timestamp_ms;      /* 0x0C: Sender local monotonic clock (ms) */
    float    distance_m;        /* 0x10: Forward ranging measurement (m) */
    float    speed_mps;         /* 0x14: Vehicle speed (meters/sec) */
    float    accel_mps2;        /* 0x18: Longitudinal acceleration (m/s^2) */
    int8_t   rssi_dbm;          /* 0x1C: RSSI of last received peer frame (dBm) */
    uint8_t  reserved[1];       /* 0x1D: Alignment padding */
    uint16_t crc16;             /* 0x1E: CRC16-CCITT covering bytes 0x00..0x1D */
} v2v_packet_t;
#pragma pack(pop)

#define V2V_PACKET_SIZE sizeof(v2v_packet_t)
#define V2V_CRC_OFFSET  (V2V_PACKET_SIZE - sizeof(uint16_t))

#ifdef __cplusplus
}
#endif



/* ==== MERGED FROM firmware/common/validation/packet_validator.h (unmodified body) ====
    Generated for standalone diagnostic sketches; sha256 recorded in README_MANUAL_FLASH.md
    ==== */

/**
 * @file packet_validator.h
 * @brief Wire-Protocol Packet Validation & Integrity Checks
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */



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


#endif /* V2V_PACKET_H */
