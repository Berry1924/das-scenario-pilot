/**
 * @file test_safety_isolation.cpp
 * @brief Host Unit Tests for Safety-Path Isolation Guarantees
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include <iostream>
#include <cassert>
#include <cstring>
#include "../common/protocol/v2v_packet.h"
#include "../common/safety/safety_isolation.h"

void test_safety_invariants() {
    std::cout << "[TEST] Checking safety-path isolation invariants..." << std::endl;
    v2v_packet_t pkt;
    memset(&pkt, 0, sizeof(v2v_packet_t));

    /* Case 1: Routine beacon without hazard */
    pkt.priority = PRIORITY_BEACON;
    pkt.hazard_flags = HAZARD_FLAG_NONE;
    assert(is_safety_critical_packet(&pkt) == false);
    assert(is_ml_throttle_allowed(&pkt) == true);
    std::cout << "  -> Routine beacons are throttle-eligible by ML." << std::endl;

    /* Case 2: Emergency priority set */
    pkt.priority = PRIORITY_EMERGENCY;
    assert(is_safety_critical_packet(&pkt) == true);
    assert(is_ml_throttle_allowed(&pkt) == false);
    std::cout << "  -> Emergency priority packets FORBID ML throttling." << std::endl;

    /* Case 3: Priority is beacon, but emergency brake flag is set */
    pkt.priority = PRIORITY_BEACON;
    pkt.hazard_flags = HAZARD_FLAG_BRAKE_ACTIVE;
    assert(is_safety_critical_packet(&pkt) == true);
    assert(is_ml_throttle_allowed(&pkt) == false);
    std::cout << "  -> Active brake flag strictly forces safety isolation." << std::endl;

    /* Case 4: Enforcing safety isolation mutates priority and hazard flags */
    pkt.priority = PRIORITY_BEACON;
    pkt.hazard_flags = HAZARD_FLAG_NONE;
    enforce_safety_isolation(&pkt, true, false);
    assert(pkt.priority == PRIORITY_EMERGENCY);
    assert((pkt.hazard_flags & HAZARD_FLAG_BRAKE_ACTIVE) != 0);
    assert(is_ml_throttle_allowed(&pkt) == false);
    std::cout << "  -> enforce_safety_isolation correctly sets emergency priority." << std::endl;

    std::cout << "  -> PASS: Safety-path isolation invariants strictly upheld." << std::endl;
}

int main() {
    std::cout << "=== RUNNING SAFETY-PATH ISOLATION TESTS ===" << std::endl;
    test_safety_invariants();
    std::cout << "=== ALL SAFETY ISOLATION TESTS PASSED! ===" << std::endl;
    return 0;
}
