/**
 * @file safety_isolation.h
 * @brief Safety-Path Isolation Guarantees for DAAS-V2V / SIH26007
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 * 
 * Enforces the core architectural safety principle:
 * Life-critical emergency packets (sudden braking, imminent collision)
 * MUST bypass all supervisory ML queues, rate limiters, and background tasks,
 * transmitting instantaneously with priority preemption.
 */

#ifndef SAFETY_ISOLATION_H
#define SAFETY_ISOLATION_H

#include "../protocol/v2v_packet.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Checks if a packet qualifies for immediate emergency safety-path transmission.
 * @param packet Pointer to the packet to inspect.
 * @return true if packet is emergency priority or contains emergency hazard flags.
 */
static inline bool is_safety_critical_packet(const v2v_packet_t* packet) {
    if (!packet) return false;
    
    /* Condition 1: Direct emergency priority */
    if (packet->priority == PRIORITY_EMERGENCY) {
        return true;
    }
    
    /* Condition 2: Emergency brake active or imminent collision flag set */
    if ((packet->hazard_flags & (HAZARD_FLAG_BRAKE_ACTIVE | HAZARD_FLAG_IMMINENT_COLLISION)) != 0) {
        return true;
    }
    
    return false;
}

/**
 * @brief Evaluates whether supervisory ML rate-adaptation may throttle this packet.
 * Invariant: Emergency packets CAN NEVER BE THROTTLED OR DELAYED.
 * @param packet Pointer to the packet.
 * @return true if ML may adapt transmission frequency; false if transmission is mandatory.
 */
static inline bool is_ml_throttle_allowed(const v2v_packet_t* packet) {
    if (is_safety_critical_packet(packet)) {
        return false; /* Hard invariant: ML throttling forbidden for safety-critical packets */
    }
    return true; /* Routine beacons may be dynamically rate-adapted */
}

/**
 * @brief Forces a packet into emergency safety-path mode if critical conditions are met.
 * @param packet Pointer to packet to mutate.
 * @param brake_active True if emergency brake switch is depressed.
 * @param imminent_collision True if local TTC is below critical safety margin.
 */
static inline void enforce_safety_isolation(v2v_packet_t* packet, bool brake_active, bool imminent_collision) {
    if (!packet) return;
    
    if (brake_active) {
        packet->priority = PRIORITY_EMERGENCY;
        packet->hazard_flags |= HAZARD_FLAG_BRAKE_ACTIVE;
    }
    
    if (imminent_collision) {
        packet->priority = PRIORITY_EMERGENCY;
        packet->hazard_flags |= HAZARD_FLAG_IMMINENT_COLLISION;
    }
}

#ifdef __cplusplus
}
#endif

#endif /* SAFETY_ISOLATION_H */
