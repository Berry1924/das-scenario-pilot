/**
 * @file test_risk_engine.cpp
 * @brief Host Unit Tests for Collision Risk Engine & Time-to-Collision (TTC)
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include <iostream>
#include <cassert>
#include <cmath>
#include "../common/protocol/v2v_packet.h"

/* Risk Engine Logic in isolation for host unit testing */
static float calculateTTC(float distance_m, float closing_speed_mps) {
    if (closing_speed_mps <= 0.1f) return 99.9f;
    if (distance_m <= 0.0f) return 0.0f;
    return distance_m / closing_speed_mps;
}

static v2v_risk_level_t classifyRisk(float distance_m, float ttc_sec, uint16_t peer_hazard_flags) {
    if ((peer_hazard_flags & HAZARD_FLAG_BRAKE_ACTIVE) != 0) {
        return RISK_LEVEL_CRITICAL;
    }
    if (distance_m <= 4.0f || ttc_sec <= 1.5f) {
        return RISK_LEVEL_CRITICAL;
    }
    if (distance_m <= 8.0f || ttc_sec <= 3.0f) {
        return RISK_LEVEL_WARNING;
    }
    if (distance_m <= 15.0f || ttc_sec <= 5.0f) {
        return RISK_LEVEL_CAUTION;
    }
    return RISK_LEVEL_SAFE;
}

void test_ttc_calculation() {
    std::cout << "[TEST] Checking TTC mathematical formula (d / v_rel)..." << std::endl;
    
    /* 30 meters at 10 m/s closing speed -> TTC = 3.0s */
    float ttc1 = calculateTTC(30.0f, 10.0f);
    assert(std::fabs(ttc1 - 3.0f) < 0.01f);

    /* 10 meters at 10 m/s closing speed -> TTC = 1.0s */
    float ttc2 = calculateTTC(10.0f, 10.0f);
    assert(std::fabs(ttc2 - 1.0f) < 0.01f);

    /* Diverging or stationary (closing speed <= 0.1 m/s) -> TTC = 99.9s (Infinite safe) */
    float ttc_safe = calculateTTC(5.0f, 0.05f);
    assert(ttc_safe >= 99.0f);

    std::cout << "  -> PASS: TTC calculations accurate." << std::endl;
}

void test_risk_classification() {
    std::cout << "[TEST] Checking multi-tier risk classification zones..." << std::endl;

    /* Zone 1: Safe (40m, TTC = 10s) */
    assert(classifyRisk(40.0f, 10.0f, HAZARD_FLAG_NONE) == RISK_LEVEL_SAFE);

    /* Zone 2: Caution (12m, TTC = 4.0s) */
    assert(classifyRisk(12.0f, 4.0f, HAZARD_FLAG_NONE) == RISK_LEVEL_CAUTION);

    /* Zone 3: Warning (6m, TTC = 2.0s) */
    assert(classifyRisk(6.0f, 2.0f, HAZARD_FLAG_NONE) == RISK_LEVEL_WARNING);

    /* Zone 4: Critical (3m, TTC = 0.8s) */
    assert(classifyRisk(3.0f, 0.8f, HAZARD_FLAG_NONE) == RISK_LEVEL_CRITICAL);

    /* Emergency Brake Preemption: Distance is 50m (far away), but peer has BRAKE flag set */
    assert(classifyRisk(50.0f, 20.0f, HAZARD_FLAG_BRAKE_ACTIVE) == RISK_LEVEL_CRITICAL);

    std::cout << "  -> PASS: Risk classification and emergency brake preemption verified." << std::endl;
}

int main() {
    std::cout << "=== RUNNING RISK ENGINE & TTC TESTS ===" << std::endl;
    test_ttc_calculation();
    test_risk_classification();
    std::cout << "=== ALL RISK ENGINE TESTS PASSED! ===" << std::endl;
    return 0;
}
