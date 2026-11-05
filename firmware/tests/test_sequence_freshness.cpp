/**
 * @file test_sequence_freshness.cpp
 * @brief Host Unit Tests for Sequence Progression and Message Age
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include <iostream>
#include <cassert>
#include <cstring>
#include "../common/protocol/v2v_packet.h"
#include "../common/validation/packet_validator.h"

void test_sequence_progression() {
    std::cout << "[TEST] Checking sequence progression and dropped packet counting..." << std::endl;
    uint32_t last_seq = 0;
    uint32_t dropped = 0;

    /* Initial packet */
    assert(v2v_validate_sequence(1, last_seq, &dropped) == true);
    assert(dropped == 0);
    last_seq = 1;

    /* Next contiguous packet */
    assert(v2v_validate_sequence(2, last_seq, &dropped) == true);
    assert(dropped == 0);
    last_seq = 2;

    /* Packet skip: sequence 2 -> sequence 6 (dropped = 3: packets 3, 4, 5) */
    assert(v2v_validate_sequence(6, last_seq, &dropped) == true);
    assert(dropped == 3);
    last_seq = 6;

    /* Duplicate sequence: sequence 6 again */
    assert(v2v_validate_sequence(6, last_seq, &dropped) == false);

    /* Out of order / replayed old sequence: sequence 4 */
    assert(v2v_validate_sequence(4, last_seq, &dropped) == false);

    std::cout << "  -> PASS: Sequence validation and drop estimation correct." << std::endl;
}

void test_message_freshness() {
    std::cout << "[TEST] Checking message age freshness threshold (500 ms)..." << std::endl;
    v2v_packet_t pkt;
    memset(&pkt, 0, sizeof(v2v_packet_t));

    pkt.magic = V2V_MAGIC_BYTE;
    pkt.protocol_version = V2V_PROTOCOL_VERSION;
    pkt.timestamp_ms = 10000;
    pkt.distance_m = 12.0f;
    v2v_sign_packet(&pkt);

    /* Arrival at 10100 ms (age = 100 ms) -> FRESH */
    assert(v2v_validate_packet(&pkt, 10100) == V2V_VALID_OK);

    /* Arrival at 10450 ms (age = 450 ms) -> FRESH */
    assert(v2v_validate_packet(&pkt, 10450) == V2V_VALID_OK);

    /* Arrival at 10600 ms (age = 600 ms > 500 ms limit) -> STALE */
    assert(v2v_validate_packet(&pkt, 10600) == V2V_ERR_STALE_TIMESTAMP);

    std::cout << "  -> PASS: Stale messages (>500ms) flagged correctly." << std::endl;
}

int main() {
    std::cout << "=== RUNNING SEQUENCE & FRESHNESS TESTS ===" << std::endl;
    test_sequence_progression();
    test_message_freshness();
    std::cout << "=== ALL SEQUENCE & FRESHNESS TESTS PASSED! ===" << std::endl;
    return 0;
}
