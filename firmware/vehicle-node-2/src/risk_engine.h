/**
 * @file risk_engine.h
 * @brief Deterministic Collision Risk & Time-to-Collision (TTC) Engine
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#ifndef RISK_ENGINE_H
#define RISK_ENGINE_H

#include <stdint.h>
#include <stdbool.h>
#include "../include/node_config.h"
#include "../../common/protocol/v2v_packet.h"

class RiskEngine {
public:
    RiskEngine();

    void evaluate(float distance_m, float closing_speed_mps, uint16_t peer_hazard_flags, bool local_brake_pressed);

    v2v_risk_level_t getRiskLevel() const { return current_risk; }
    float getTTC() const { return current_ttc_sec; }
    bool isImminentCollision() const { return current_risk == RISK_LEVEL_CRITICAL; }

    static float calculateTTC(float distance_m, float closing_speed_mps);
    static v2v_risk_level_t classifyRisk(float distance_m, float ttc_sec, uint16_t peer_hazard_flags);

private:
    v2v_risk_level_t current_risk;
    float current_ttc_sec;
};

#endif /* RISK_ENGINE_H */
