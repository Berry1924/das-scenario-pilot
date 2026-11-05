/**
 * @file run_all_firmware_tests.cpp
 * @brief Master Test Runner for Embedded Firmware Host Unit Tests
 * @copyright Team IGRIS07 - SKP Engineering College (NMDC SIH26007)
 */

#include <iostream>
#include <cstdlib>

int main() {
    std::cout << "=========================================================" << std::endl;
    std::cout << "  DAAS-V2V / SIH26007 EMBEDDED ALGORITHM TEST RUNNER    " << std::endl;
    std::cout << "=========================================================" << std::endl;

    const char* tests[] = {
        "firmware/tests/test_wire_protocol.exe",
        "firmware/tests/test_sequence_freshness.exe",
        "firmware/tests/test_risk_engine.exe",
        "firmware/tests/test_hazard_decay.exe",
        "firmware/tests/test_safety_isolation.exe"
    };

    int total_suites = sizeof(tests) / sizeof(tests[0]);
    int passed_suites = 0;

    for (int i = 0; i < total_suites; i++) {
        std::cout << "\n>>> Executing Suite [" << (i + 1) << "/" << total_suites << "]: " << tests[i] << "..." << std::endl;
        int ret = std::system(tests[i]);
        if (ret == 0) {
            passed_suites++;
            std::cout << ">>> Suite [" << (i + 1) << "] STATUS: SUCCESS (Code 0)" << std::endl;
        } else {
            std::cerr << ">>> Suite [" << (i + 1) << "] STATUS: FAILED (Code " << ret << ")" << std::endl;
        }
    }

    std::cout << "\n=========================================================" << std::endl;
    std::cout << "  TEST RESULTS: " << passed_suites << " / " << total_suites << " SUITES PASSED" << std::endl;
    std::cout << "=========================================================" << std::endl;

    return (passed_suites == total_suites) ? 0 : 1;
}
