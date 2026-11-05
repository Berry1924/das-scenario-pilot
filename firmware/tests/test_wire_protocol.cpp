/**
 * @file test_wire_protocol.cpp
 * @brief Host Unit Tests for V2V Wire Protocol, CRC16, and Bounds Checking
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include <iostream>
#include <cassert>
#include <cstring>
#include "../common/protocol/v2v_packet.h"
#include "../common/validation/packet_validator.h"

void test_packet_size_and_alignment() {
    std::cout << "[TEST] Checking packet size and byte alignment..." << std::endl;
    assert(sizeof(v2v_packet_t) == 32);
    assert(V2V_PACKET_SIZE == 32);
    assert(V2V_CRC_OFFSET == 30);
    std::cout << "  -> PASS: v2v_packet_t is exactly 32 bytes packed." << std::endl;
}

void test_crc16_integrity() {
    std::cout << "[TEST] Checking CRC16 calculation and bit-flip detection..." << std::endl;
    v2v_packet_t pkt;
    memset(&pkt, 0, sizeof(v2v_packet_t));

    pkt.magic = V2V_MAGIC_BYTE;
    pkt.protocol_version = V2V_PROTOCOL_VERSION;
    pkt.priority = PRIORITY_BEACON;
    pkt.sender_id = 1;
    pkt.target_id = 2;
    pkt.vehicle_type = VEHICLE_TYPE_HAUL_DUMPER_100T;
    pkt.seq_num = 100;
    pkt.timestamp_ms = 5000;
    pkt.distance_m = 18.5f;
    pkt.speed_mps = 8.33f;
    pkt.accel_mps2 = -0.5f;

    /* Sign packet */
    v2v_sign_packet(&pkt);
    assert(pkt.crc16 != 0);

    /* Validate unmodified packet */
    v2v_validation_result_t res = v2v_validate_packet(&pkt, 5100);
    assert(res == V2V_VALID_OK);
    std::cout << "  -> PASS: Valid packet passes CRC16 verification." << std::endl;

    /* Inject 1-bit corruption in speed field */
    pkt.speed_mps = 8.34f;
    v2v_validation_result_t corrupt_res = v2v_validate_packet(&pkt, 5100);
    assert(corrupt_res == V2V_ERR_CRC_MISMATCH);
    std::cout << "  -> PASS: Bit-flip correctly rejected with CRC mismatch." << std::endl;
}

void test_magic_and_version_rejection() {
    std::cout << "[TEST] Checking invalid magic byte and version rejection..." << std::endl;
    v2v_packet_t pkt;
    memset(&pkt, 0, sizeof(v2v_packet_t));

    pkt.magic = 0xAA; /* Bad magic byte */
    pkt.protocol_version = V2V_PROTOCOL_VERSION;
    v2v_sign_packet(&pkt);
    assert(v2v_validate_packet(&pkt, 0) == V2V_ERR_BAD_MAGIC);

    pkt.magic = V2V_MAGIC_BYTE;
    pkt.protocol_version = 0x99; /* Unsupported version */
    v2v_sign_packet(&pkt);
    assert(v2v_validate_packet(&pkt, 0) == V2V_ERR_UNSUPPORTED_VERSION);

    std::cout << "  -> PASS: Bad magic and unsupported versions correctly rejected." << std::endl;
}

void test_kinematic_bounds() {
    std::cout << "[TEST] Checking kinematic physical bounds validation..." << std::endl;
    v2v_packet_t pkt;
    memset(&pkt, 0, sizeof(v2v_packet_t));

    pkt.magic = V2V_MAGIC_BYTE;
    pkt.protocol_version = V2V_PROTOCOL_VERSION;
    pkt.distance_m = -5.0f; /* Impossible negative distance */
    v2v_sign_packet(&pkt);
    assert(v2v_validate_packet(&pkt, 0) == V2V_ERR_OUT_OF_BOUNDS);

    pkt.distance_m = 10.0f;
    pkt.speed_mps = 200.0f; /* Unrealistic speed for mining dumper */
    v2v_sign_packet(&pkt);
    assert(v2v_validate_packet(&pkt, 0) == V2V_ERR_OUT_OF_BOUNDS);

    std::cout << "  -> PASS: Impossible kinematics rejected by bounds validator." << std::endl;
}

int main() {
    std::cout << "=== RUNNING WIRE PROTOCOL & CRC16 TESTS ===" << std::endl;
    test_packet_size_and_alignment();
    test_crc16_integrity();
    test_magic_and_version_rejection();
    test_kinematic_bounds();
    std::cout << "=== ALL WIRE PROTOCOL TESTS PASSED! ===" << std::endl;
    return 0;
}
