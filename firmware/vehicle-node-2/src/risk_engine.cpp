/**
 * @file risk_engine.cpp
 * @brief Deterministic Collision Risk & Time-to-Collision (TTC) Engine Implementation
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include "risk_engine.h"

RiskEngine::RiskEngine()
    : current_risk(RISK_LEVEL_SAFE),
      current_ttc_sec(99.9f) {
}

float RiskEngine::calculateTTC(float distance_m, float closing_speed_mps) {
    if (closing_speed_mps <= 0.1f) {
        return 99.9f; /* Vehicles are diverging or stationary relative to each other */
    }
    if (distance_m <= 0.0f) {
        return 0.0f;
    }
    return distance_m / closing_speed_mps;
}

v2v_risk_level_t RiskEngine::classifyRisk(float distance_m, float ttc_sec, uint16_t peer_hazard_flags) {
    /* Critical Condition 1: Peer has active emergency brake */
    if ((peer_hazard_flags & HAZARD_FLAG_BRAKE_ACTIVE) != 0) {
        return RISK_LEVEL_CRITICAL;
    }

    /* Critical Condition 2: Imminent geometric collision */
    if (distance_m <= THRESHOLD_DIST_CRITICAL_M || ttc_sec <= THRESHOLD_TTC_CRITICAL_S) {
        return RISK_LEVEL_CRITICAL;
    }

    /* Warning Zone */
    if (distance_m <= THRESHOLD_DIST_WARNING_M || ttc_sec <= THRESHOLD_TTC_WARNING_S) {
        return RISK_LEVEL_WARNING;
    }

    /* Caution Zone */
    if (distance_m <= THRESHOLD_DIST_CAUTION_M || ttc_sec <= THRESHOLD_TTC_CAUTION_S) {
        return RISK_LEVEL_CAUTION;
    }

    return RISK_LEVEL_SAFE;
}

void RiskEngine::evaluate(float distance_m, float closing_speed_mps, uint16_t peer_hazard_flags, bool local_brake_pressed) {
    current_ttc_sec = calculateTTC(distance_m, closing_speed_mps);
    current_risk = classifyRisk(distance_m, current_ttc_sec, peer_hazard_flags);

    /* If local driver slammed brake, local state indicates active hazard */
    if (local_brake_pressed && current_risk < RISK_LEVEL_WARNING) {
        current_risk = RISK_LEVEL_WARNING;
    }
}
