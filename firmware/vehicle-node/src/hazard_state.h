/**
 * @file hazard_state.h
 * @brief Hazard State Memory & Anti-Flicker Temporal Holding Subsystem
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef HAZARD_STATE_H
#define HAZARD_STATE_H

#include <stdint.h>
#include <stdbool.h>
#include "../include/node_config.h"

class HazardStateManager {
public:
    HazardStateManager();
    void update(uint32_t current_time_ms);
    void triggerHazard(uint16_t hazard_flags, uint32_t current_time_ms);

    bool isHazardActive() const { return active_latched; }
    uint16_t getLatchedFlags() const { return latched_flags; }
    uint32_t getTimeRemainingMs(uint32_t current_time_ms) const;

private:
    bool active_latched;
    uint16_t latched_flags;
    uint32_t latch_start_time_ms;
};

#endif /* HAZARD_STATE_H */
