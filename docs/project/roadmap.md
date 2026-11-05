# Engineering Roadmap & Evolution Phases

**Project:** DAAS-V2V / SIH26007 Mine Vehicle Safety System  
**Document Type:** Strategic Development & Technology Evolution Roadmap  
**Current Active Phase:** Phase 3 (SIH26007 Bench Physical Prototype)  

---

## 1. Evolution Overview

```
+---------------------------------------------------------------------------------------------------+
|                                 TECHNOLOGY EVOLUTION TIMELINE                                     |
+---------------------------------------------------------------------------------------------------+
|  PHASE 1: Foundations (2024-2025)                                                                 |
|  - Texas Instruments CC2500 2.4 GHz SPI Transceiver                                              |
|  - Point-to-point basic payload transmission                                                      |
|  - Evaluated basic RF packet error rates and microcontroller interfacing                         |
|  - Status: ARCHIVED / PRESERVED IN DOCUMENTATION                                                  |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|  PHASE 2: DAAS-V2V ML & Network Intelligence Engine (Mid 2026)                                    |
|  - High-density vehicular network simulation (85,248 synthetic records)                           |
|  - Machine learning models for channel density, congestion, and beacon rate prediction             |
|  - Telemetry pipeline, database schemas, and FastAPI ingestion server                             |
|  - Benchmarked 99.72% accuracy and 9.93 ms host inference latency                                 |
|  - Status: FULLY IMPLEMENTED (HOST / SYNTHETIC BENCHMARK)                                         |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|  PHASE 3: SIH26007 Cooperative Mine Physical Prototype (CURRENT STATE)                            |
|  - Dual ESP32-WROOM-32 hardware nodes communicating via ESP-NOW 2.4 GHz                          |
|  - Local physical sensing: HC-SR04 ultrasonic surrogate & brake event switch                      |
|  - In-cab HMI: SSD1306 0.96" I2C OLED display + multi-tone buzzer + red/green warning LEDs        |
|  - Wire Protocol v2.0 with CRC16, monotonic sequence numbers, message age checks                  |
|  - Deterministic embedded risk engine (TTC, proximity zones, hazard memory holding register)      |
|  - Autonomous fail-safe fallback watchdog (2.5-second timeout on radio link loss)                 |
|  - Status: FULLY FUNCTIONAL BENCH PROTOTYPE                                                       |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|  PHASE 4: Industrial Ruggedization & Scale-Up (PLANNED / ROADMAP)                                 |
|  - Sensor Fusion: 77 GHz mmWave industrial radar (TI AWR1843) + uncooled LWIR thermal camera       |
|  - High-Precision Localization: Dual-antenna RTK-GNSS + 6-axis IMU dead reckoning                |
|  - Production Radio: 3GPP C-V2X (PC5 Sidelink) in 5.9 GHz ITS band (Quectel AG15 OBU)             |
|  - Enclosure & Hardening: IP67-rated cast aluminium chassis, M12 industrial connectors, 12V/24V   |
|    vehicle transient surge protection (ISO 7637-2)                                                |
|  - Mining Compliance: DGMS (Directorate General of Mines Safety) approval & NMDC pilot trials     |
|  - Status: ARCHITECTURALLY SPECIFIED (NOT YET VALIDATED IN MINES)                                 |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Phase-by-Phase Deliverables & Milestones

### Phase 1: Historical Proof-of-Concept (CC2500)
- **Goal:** Investigate basic RF propagation and raw packet latency across simple wireless modules.
- **Hardware:** Microcontroller + CC2500 2.4 GHz SPI transceiver.
- **Outcomes:** Discovered limitation in bit-rate flexibility, antenna range, and lack of integrated protocol stack. Established need for modern SoC with native Wi-Fi/ESP-NOW hardware.
- **Artifacts:** Historical design notes preserved in `research/reports/V2V Communication Plan and Guide.docx`.

### Phase 2: DAAS-V2V ML & Network Intelligence Engine
- **Goal:** Solve communication bottleneck in congested vehicular ad-hoc networks (VANETs).
- **Deliverables:**
  - Synthetic dataset generator creating realistic speed, density, RSSI, and SNR parameters (`synthetic_vanet.csv`).
  - XGBoost multi-target classifiers for network congestion and vehicle density.
  - Telemetry ingestion gateway and database models for fleet supervision.
- **Verification:** 85,248 evaluated records, ROC-AUC 0.9301, host inference latency 9.93 ms.

### Phase 3: SIH26007 Mine Safety Prototype (Current Milestone)
- **Goal:** Adapt DAAS architecture specifically for open-cast iron ore mine hazards under SIH Problem Statement SIH26007.
- **Deliverables:**
  - Two discrete physical ESP32 nodes (Leader Node 1 and Follower Node 2) mounted on breadboards with full wiring harness.
  - Wire protocol struct with magic byte `0xD4`, CRC16 checksum, priority header, and hazard payload.
  - Ultrasonic sensor integration for near-field distance measurement.
  - Push-button emergency brake simulation with instant priority preemption.
  - Cockpit HMI showing live status (`SAFE`, `CAUTION`, `WARNING`, `CRITICAL`), range, and TTC.
  - Heartbeat monitor transitioning to autonomous degraded mode upon radio dropout.
- **Verification:** Laboratory bench demonstrations, multi-node serial captures, photograph gallery in `media/prototype/`.

### Phase 4: Industrial Scale-Up & Mining Field Trials (Upcoming)
- **Target Venue:** NMDC Limited Open Cast Iron Ore Mines (Kirandul / Bailadila Complex, Chhattisgarh, India).
- **Key Technical Transitions:**
  1. *Acoustic to Electromagnetic Ranging:* Replace HC-SR04 ultrasonic sensor with automotive-grade 77 GHz mmWave radar immune to airborne dust and ambient mine noise.
  2. *ESP-NOW to Sidelink PC5:* Move from 2.4 GHz unlicensed Wi-Fi action frames to dedicated 5.9 GHz C-V2X PC5 for 500m+ reliable range around pit benches.
  3. *Surrogate Brake to J1939 CAN Bus:* Interface directly with vehicle CAN bus via ISO 11898 transceiver to read actual hydraulic brake pressure, retarder status, and wheel speed.
  4. *Regulatory Certification:* Fulfill DGMS circular requirements for non-intrinsically safe and flameproof equipment in surface mines.
