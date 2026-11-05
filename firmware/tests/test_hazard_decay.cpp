/**
 * @file test_hazard_decay.cpp
 * @brief Host Unit Tests for Hazard Memory Latching & Temporal Decay
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include <iostream>
#include <cassert>
#include "../common/protocol/v2v_packet.h"

#define LATCH_DURATION_MS 1500

class TestHazardState {
public:
    TestHazardState() : active(false), flags(0), start_time_ms(0) {}

    void trigger(uint16_t new_flags, uint32_t now_ms) {
        if (new_flags != 0) {
            active = true;
            flags |= new_flags;
            start_time_ms = now_ms;
        }
    }

    void update(uint32_t now_ms) {
        if (active && (now_ms - start_time_ms >= LATCH_DURATION_MS)) {
            active = false;
            flags = 0;
        }
    }

    bool isActive() const { return active; }
    uint16_t getFlags() const { return flags; }

private:
    bool active;
    uint16_t flags;
    uint32_t start_time_ms;
};

void test_hazard_latch_and_decay() {
    std::cout << "[TEST] Checking hazard state latching and 1500ms decay..." << std::endl;
    TestHazardState hz;

    assert(!hz.isActive());

    /* Event occurs at t = 1000 ms */
    hz.trigger(HAZARD_FLAG_BRAKE_ACTIVE, 1000);
    assert(hz.isActive());
    assert(hz.getFlags() == HAZARD_FLAG_BRAKE_ACTIVE);

    /* After 500 ms (t = 1500 ms) -> Still active (anti-flicker protection) */
    hz.update(1500);
    assert(hz.isActive());

    /* After 1400 ms (t = 2400 ms) -> Still active */
    hz.update(2400);
    assert(hz.isActive());

    /* At t = 2500 ms (elapsed = 1500 ms) -> Decays to safe */
    hz.update(2500);
    assert(!hz.isActive());
    assert(hz.getFlags() == 0);

    std::cout << "  -> PASS: Hazard correctly latched for 1500 ms and decayed to safe." << std::endl;
}

int main() {
    std::cout << "=== RUNNING HAZARD STATE & DECAY TESTS ===" << std::endl;
    test_hazard_latch_and_decay();
    std::cout << "=== ALL HAZARD DECAY TESTS PASSED! ===" << std::endl;
    return 0;
}
