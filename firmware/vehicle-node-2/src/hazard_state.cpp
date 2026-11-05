/**
 * @file hazard_state.cpp
 * @brief Hazard State Memory & Anti-Flicker Temporal Holding Implementation
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include "hazard_state.h"

HazardStateManager::HazardStateManager()
    : active_latched(false),
      latched_flags(HAZARD_FLAG_NONE),
      latch_start_time_ms(0) {
}

void HazardStateManager::triggerHazard(uint16_t hazard_flags, uint32_t current_time_ms) {
    if (hazard_flags != HAZARD_FLAG_NONE) {
        active_latched = true;
        latched_flags |= hazard_flags;
        latch_start_time_ms = current_time_ms;
    }
}

void HazardStateManager::update(uint32_t current_time_ms) {
    if (active_latched) {
        if (current_time_ms - latch_start_time_ms >= HAZARD_LATCH_DURATION_MS) {
            /* Grace duration expired: decay hazard state */
            active_latched = false;
            latched_flags = HAZARD_FLAG_NONE;
        }
    }
}

uint32_t HazardStateManager::getTimeRemainingMs(uint32_t current_time_ms) const {
    if (!active_latched) return 0;
    uint32_t elapsed = current_time_ms - latch_start_time_ms;
    if (elapsed >= HAZARD_LATCH_DURATION_MS) return 0;
    return HAZARD_LATCH_DURATION_MS - elapsed;
}
