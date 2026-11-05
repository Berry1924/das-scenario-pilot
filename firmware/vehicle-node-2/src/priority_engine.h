/**
 * @file priority_engine.h
 * @brief Safety-Path Priority Dispatcher & Rate Control Engine
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef PRIORITY_ENGINE_H
#define PRIORITY_ENGINE_H

#include <stdint.h>
#include <stdbool.h>
#include "../include/node_config.h"
#include "../../common/protocol/v2v_packet.h"
#include "../../common/safety/safety_isolation.h"

class PriorityEngine {
public:
    PriorityEngine();

    bool shouldTransmit(uint32_t current_time_ms, bool is_emergency);
    void recordTransmission(uint32_t current_time_ms);
    void adaptBeaconRate(float target_rate_hz);

    uint32_t getTxIntervalMs() const { return current_interval_ms; }
    v2v_priority_t determinePacketPriority(bool brake_active, bool imminent_collision) const;

private:
    uint32_t current_interval_ms;
    uint32_t last_tx_time_ms;
    uint32_t last_emergency_tx_time_ms;
};

#endif /* PRIORITY_ENGINE_H */
