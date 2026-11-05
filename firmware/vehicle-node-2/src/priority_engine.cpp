/**
 * @file priority_engine.cpp
 * @brief Safety-Path Priority Dispatcher & Rate Control Engine Implementation
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include "priority_engine.h"

PriorityEngine::PriorityEngine()
    : current_interval_ms(DEFAULT_TX_INTERVAL_MS),
      last_tx_time_ms(0),
      last_emergency_tx_time_ms(0) {
}

v2v_priority_t PriorityEngine::determinePacketPriority(bool brake_active, bool imminent_collision) const {
    if (brake_active || imminent_collision) {
        return PRIORITY_EMERGENCY;
    }
    return PRIORITY_BEACON;
}

bool PriorityEngine::shouldTransmit(uint32_t current_time_ms, bool is_emergency) {
    if (is_emergency) {
        /* Safety-path preemption: Allow rapid emergency transmission bursts up to 20 Hz (50 ms min gap) */
        if (current_time_ms - last_emergency_tx_time_ms >= MIN_TX_INTERVAL_MS) {
            return true;
        }
        return false;
    }

    /* Routine periodic beacon check */
    if (current_time_ms - last_tx_time_ms >= current_interval_ms) {
        return true;
    }

    return false;
}

void PriorityEngine::recordTransmission(uint32_t current_time_ms) {
    last_tx_time_ms = current_time_ms;
}

void PriorityEngine::adaptBeaconRate(float target_rate_hz) {
    if (target_rate_hz <= 0.0f) return;

    uint32_t interval = (uint32_t)(1000.0f / target_rate_hz);
    if (interval < MIN_TX_INTERVAL_MS) interval = MIN_TX_INTERVAL_MS;
    if (interval > MAX_TX_INTERVAL_MS) interval = MAX_TX_INTERVAL_MS;

    current_interval_ms = interval;
}
