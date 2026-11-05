/**
 * @file fallback_manager.h
 * @brief Fail-Safe Watchdog & Degraded Autonomous Fallback Subsystem
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef FALLBACK_MANAGER_H
#define FALLBACK_MANAGER_H

#include <stdint.h>
#include <stdbool.h>
#include "../include/node_config.h"

class FallbackManager {
public:
    FallbackManager();

    void recordPeerHeartbeat(uint32_t current_time_ms);
    void update(uint32_t current_time_ms);

    bool isFallbackActive() const { return fallback_active; }
    uint32_t getSilenceDurationMs(uint32_t current_time_ms) const;

private:
    bool fallback_active;
    uint32_t last_heartbeat_time_ms;
};

#endif /* FALLBACK_MANAGER_H */
