# Changelog

All notable changes to the DAAS-V2V / SIH26007 project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] - 2026-09-29

### Added
- **Monorepo Unification:** Consolidated historical CC2500 research, DAAS-V2V ML intelligence pipeline, and SIH26007 cooperative mine safety prototype into a single clean architecture.
- **Wire Protocol v2.0:** Defined packed 32-byte wire frame with magic byte `0xD4`, CRC16-CCITT payload checksum, monotonic sequence counters, and message freshness evaluation.
- **Safety-Path Isolation:** Implemented dual-path priority dispatcher guaranteeing that life-critical emergency braking packets bypass all ML queues with zero delay.
- **Embedded Risk Engine:** Implemented deterministic Time-to-Collision (TTC) algorithm and multi-zone proximity risk classification (`SAFE`, `CAUTION`, `WARNING`, `CRITICAL`).
- **Hazard Memory & Decay:** Added 1500 ms anti-flicker temporal holding register to prevent warning strobe during intermittent RF packet dropouts.
- **Autonomous Fallback Watchdog:** Added 2500 ms silence watchdog that automatically switches node into degraded autonomous sensing upon peer RF loss.
- **Host Unit Test Suite:** Implemented 5 native C++ unit test suites (`test_wire_protocol.cpp`, `test_sequence_freshness.cpp`, `test_risk_engine.cpp`, `test_hazard_decay.cpp`, `test_safety_isolation.cpp`) and master Python runner (`run_tests.py`).
- **CI/CD Automation:** Added GitHub Actions workflows for firmware test compilation, Python ML testing, and documentation integrity verification.
- **Physical Prototype Evidence:** Cataloged and annotated 8 authentic high-resolution bench photographs depicting the operational dual-ESP32 testbed.
- **Comprehensive Documentation:** Created over 20 detailed specifications covering system architecture, claim register, ADRs, mine adaptation analysis, and security roadmap.

### Changed
- **Pin Mapping Resolution (ADR-005):** Resolved legacy pin collision between `BRAKE_PIN` and `LED_DANGER_PIN` (both previously assigned to GPIO 4 in `daas_v1.ino`). Formalized GPIO 19 for Brake Input and GPIO 4 for Danger LED.
- **Modular Firmware Architecture:** Refactored monolithic `.ino` sketches into clean, modular C++ subsystems (`sensor_manager`, `v2v_protocol`, `risk_engine`, `priority_engine`, `hazard_state`, `fallback_manager`, `hmi`, `telemetry`).

### Removed / Archived
- Isolated out-of-scope EC25C09 electronics circuit lab manuals into `archive/ec25c09-lab-manual/`.
- Isolated generic SIH scraping scripts into `archive/sih2026-scraping/`.
- Archived legacy DAAS documentation into `archive/superseded-documents/legacy-daas-docs/`.

---

## [1.0.0] - 2026-08-15

### Added
- Initial DAAS-V2V ML intelligence pipeline, synthetic dataset generator (85,248 records), and XGBoost density/congestion models.
- Preliminary single-file Arduino sketches (`daas_v1.ino`, `daas_v2.ino`) demonstrating basic ESP-NOW communication.
