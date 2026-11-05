/**
 * @file telemetry_types.h
 * @brief Telemetry Structures & Formats for Host Serial Streaming
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef TELEMETRY_TYPES_H
#define TELEMETRY_TYPES_H

#include <stdint.h>
#include <stdbool.h>
#include "../protocol/v2v_packet.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Local Node Runtime Telemetry State
 */
typedef struct {
    uint32_t uptime_ms;
    uint8_t  node_id;
    uint8_t  vehicle_type;
    bool     brake_switch_active;
    float    local_distance_m;
    float    estimated_speed_mps;
    
    /* RF Network Metrics */
    uint32_t packets_sent;
    uint32_t packets_received;
    uint32_t packets_dropped;
    uint32_t crc_errors;
    int8_t   last_peer_rssi;
    uint32_t last_peer_rx_timestamp;
    
    /* Risk Engine State */
    v2v_risk_level_t active_risk_level;
    float            calculated_ttc_sec;
    bool             hazard_latch_active;
    bool             fallback_mode_active;
    
    /* DAAS Adaptation State */
    float    target_tx_rate_hz;
    uint32_t current_tx_interval_ms;
} node_telemetry_state_t;

#ifdef __cplusplus
}
#endif

#endif /* TELEMETRY_TYPES_H */
