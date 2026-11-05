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

#endif /* V2V_PACKET_H */
