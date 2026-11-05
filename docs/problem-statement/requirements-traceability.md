# Requirements Traceability Matrix (RTM)

**Project:** DAAS-V2V / SIH26007 Mine Safety System  
**Baseline Document:** SIH26007 Problem Statement Specification  
**Document Type:** Engineering Traceability & Verification Register  

---

## 1. Traceability Matrix

| Req ID | Requirement Description | Architecture Component | Source Code / File | Verification Method | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **REQ-01** | **Direct Peer Detection in Zero Visibility:** Detect preceding/oncoming vehicles without relying on line-of-sight optical visibility. | RF Communication Layer (ESP-NOW 2.4 GHz) | `firmware/vehicle-node/src/v2v_protocol.cpp`<br>`firmware/common/protocol/v2v_packet.h` | Lab bench RF distance test across two physical nodes (50m LOS). | `PROTOTYPE/EXPERIMENTAL` |
| **REQ-02** | **Emergency Braking Preemption:** Broadcast sudden stop or hard braking alerts instantaneously with sub-10 ms latency. | Safety-Path Isolation Logic | `firmware/common/safety/safety_isolation.h`<br>`firmware/vehicle-node/src/priority_engine.cpp` | Latency capture; FreeRTOS queue bypass verification. | `IMPLEMENTED` |
| **REQ-03** | **Collision Risk Assessment (TTC):** Continuously calculate Time-to-Collision and classify risk into discrete operational zones. | Embedded Risk Engine | `firmware/vehicle-node/src/risk_engine.cpp`<br>`firmware/tests/test_risk_engine.cpp` | Deterministic unit tests with varying distance/velocity deltas. | `IMPLEMENTED` |
| **REQ-04** | **In-Cab Driver Guidance (HMI):** Provide visual alerts, distance readouts, and audible warning cadences inside the cockpit. | Cockpit HMI Subsystem | `firmware/vehicle-node/src/hmi.cpp`<br>`hardware/photos/hmi-display.jpg` | Physical bench validation with SSD1306 OLED and active buzzer. | `PROTOTYPE/EXPERIMENTAL` |
| **REQ-05** | **Fail-Safe Fallback on Link Loss:** Detect peer silence and switch to local autonomous sensing within 2.5 seconds without silent failure. | Fallback Watchdog Manager | `firmware/vehicle-node/src/fallback_manager.cpp`<br>`firmware/tests/test_fallback.cpp` | Power-disconnect test of peer node; watchdog timer timeout trigger. | `IMPLEMENTED` |
| **REQ-06** | **Anti-Flicker Warning Stability:** Prevent intermittent packet loss or RF jitter from causing visual warning strobe. | Hazard Memory Register | `firmware/vehicle-node/src/hazard_state.cpp`<br>`firmware/tests/test_hazard_state.cpp` | Packet drop simulation injection test during active hazard. | `IMPLEMENTED` |
| **REQ-07** | **Mine Operations Telemetry:** Export structured vehicle states, sensor measurements, and RF metrics for mine dispatch supervision. | Telemetry Serial Bridge | `firmware/vehicle-node/src/telemetry.cpp`<br>`tools/telemetry/esp32_gateway.py` | Real-time JSON line parsing and database ingestion at 115200 baud. | `IMPLEMENTED` |
| **REQ-08** | **RF Channel Congestion Control:** Dynamically adapt normal beaconing rates based on local vehicle density and RF channel state. | DAAS-V2V ML Adaptive Engine | `ml/src/daas/policy/adaptive.py`<br>`ml/src/daas/inference/engine.py` | Automated test suite (`ml/tests/unit/test_policy.py`) on 85,248 records. | `IMPLEMENTED (HOST/SIM)` |
| **REQ-09** | **All-Weather Penetrating Sensing:** High-resolution range and velocity measurement through heavy dust and fog using 77 GHz mmWave radar. | Modular Sensor Abstraction | `firmware/vehicle-node/src/sensor_manager.h` | Interface contract specified; HC-SR04 ultrasonic surrogate on bench. | `PLANNED` |
| **REQ-10** | **Mining Environmental Hardening:** IP67 enclosure, 24V vehicle power transient suppression, and DGMS compliance for open-cast mines. | Production Hardware Design | `docs/architecture/embedded-architecture.md` | Electrical schematics and certification roadmap documentation. | `FUTURE / NOT VALIDATED` |

---

## 2. Verification Summary

- **Total Requirements:** 10
- **Fully Implemented in Software / Unit Tested:** 5 (REQ-02, REQ-03, REQ-05, REQ-06, REQ-07)
- **Functional on Physical Bench Prototype:** 3 (REQ-01, REQ-04, REQ-08 simulation)
- **Planned / Architectural Interface Defined:** 1 (REQ-09)
- **Future / Production Mining Certification:** 1 (REQ-10)
- **Field Tested in Commercial Mine:** 0 (Explicitly zero; field trials are pending Phase 4)
