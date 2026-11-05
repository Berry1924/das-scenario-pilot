/**
 * @file fallback_manager.cpp
 * @brief Fail-Safe Watchdog & Degraded Autonomous Fallback Implementation
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include "fallback_manager.h"

FallbackManager::FallbackManager()
    : fallback_active(true), /* Start in fallback until first valid peer heartbeat */
      last_heartbeat_time_ms(0) {
}

void FallbackManager::recordPeerHeartbeat(uint32_t current_time_ms) {
    last_heartbeat_time_ms = current_time_ms;
    fallback_active = false;
}

void FallbackManager::update(uint32_t current_time_ms) {
    if (!fallback_active) {
        if (current_time_ms - last_heartbeat_time_ms >= FALLBACK_TIMEOUT_MS) {
            /* Peer silence exceeded safety timeout */
            fallback_active = true;
        }
    }
}

uint32_t FallbackManager::getSilenceDurationMs(uint32_t current_time_ms) const {
    if (last_heartbeat_time_ms == 0) return 0xFFFFFFFF;
    if (current_time_ms < last_heartbeat_time_ms) return 0;
    return current_time_ms - last_heartbeat_time_ms;
}
