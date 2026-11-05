# Project Implementation Status Register

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Safety System  
**Organization:** Team IGRIS07, SKP Engineering College (under NMDC Limited / Ministry of Steel SIH26007 Problem Statement)  
**Document Classification:** Engineering Truth & Status Ledger  
**Last Updated:** September 2026  
**Repository Branch:** `feature/repository-reengineering`

---

## 1. Status Taxonomy

To ensure absolute engineering and scientific transparency, every module, subsystem, and algorithmic component in this repository is categorized under one of five strict statuses:

| Status Code | Definition | Allowed Evidence Types |
| :--- | :--- | :--- |
| `IMPLEMENTED` | Completely written, unit-tested, and functional in software or bench testing. | Source code, automated tests, test execution logs. |
| `PROTOTYPE/EXPERIMENTAL` | Functional on physical bench hardware using surrogate sensors or constrained RF environments. Not industrial-hardened. | Hardware schematics, bench firmware, physical bench photographs, oscilloscope/serial logs. |
| `PLANNED` | Fully architected with interface contracts and data schemas specified; pending implementation. | Architecture diagrams, packet schemas, interface header files. |
| `FUTURE` | Long-term operational vision requiring external hardware or production infrastructure. | Technical specifications, standards references. |
| `NOT VALIDATED` | Explicitly demarcates conditions or environments where the system has NOT been tested. | Negative verification register, safety disclaimers. |

---

## 2. Subsystem Status Matrix

### 2.1 Communication & Protocol Layer

| Subsystem / Feature | Current Status | Description & Engineering Evidence | Next Milestone |
| :--- | :--- | :--- | :--- |
| **ESP-NOW Physical Layer** | `PROTOTYPE/EXPERIMENTAL` | 2.4 GHz 802.11 action frames on fixed Channel 1. Peer-to-peer unicast between 2 ESP32 nodes. Range ~50m bench line-of-sight. | Implement dynamic channel agility and RSSI filtering. |
| **V2V Wire Protocol v2.0** | `IMPLEMENTED` | Packed struct (`v2v_packet_t`) with magic byte `0xD4`, CRC16 checksum, monotonic sequence numbers, message age calculation, priority classes (`0x00`-`0x03`). | Multi-hop mesh relay header support. |
| **Safety-Path Isolation** | `IMPLEMENTED` | Emergency hazard messages (sudden brake, collision warning) completely bypass ML rate-adaptation and transmit instantaneously via `PRIORITY_EMERGENCY`. | Dual-core FreeRTOS task pinning to core 0. |
| **Packet Sequence Validation** | `IMPLEMENTED` | Sender-tracked monotonic sequences detect packet loss, duplicate packets, and out-of-order delivery. | Circular bitmap for out-of-order window tracking. |
| **CC2500 RF Subsystem** | `ARCHIVED / PHASE 1` | Historical 2.4 GHz SPI transceiver evaluated in preliminary prototype. Superseded by integrated ESP32 Wi-Fi PHY. | Fully preserved in documentation for research lineage. |
| **3GPP C-V2X (PC5 Direct)** | `FUTURE` | Sidelink communication operating in ITS 5.9 GHz band for industrial mine haul fleets. Requires C-V2X OBU modules (e.g. Quectel AG15). | Production hardware procurement. |

### 2.2 Sensing & Perception Layer

| Subsystem / Feature | Current Status | Description & Engineering Evidence | Next Milestone |
| :--- | :--- | :--- | :--- |
| **Ultrasonic Distance Sensing** | `PROTOTYPE/EXPERIMENTAL` | HC-SR04 ultrasonic sensor (0.05m – 4.0m) measuring range to obstacles. Used strictly as a low-cost bench surrogate for obstacle proximity. | Median filtering and echo timeout hardening. |
| **Brake Switch Telemetry** | `PROTOTYPE/EXPERIMENTAL` | Tactile push button generating discrete binary event (`0` = Normal, `1` = Hard Brake) simulating operator emergency stop. | Hall-effect pedal sensor with analog travel measurement. |
| **mmWave 77 GHz Radar** | `PLANNED` | Heavy industrial radar for penetrating thick fog, airborne dust, and rain in open-pit iron ore mines. Schema accommodates range, velocity, and azimuth. | AWR1843 Texas Instruments radar evaluation kit integration. |
| **Long-Wave Infrared (LWIR)** | `PLANNED` | Uncooled thermal imaging core (e.g., FLIR Boson) to detect haul truck heat signatures and pedestrian personnel through zero-visibility dust clouds. | Thermal camera integration with edge tensor processing. |
| **GNSS / RTK Localization** | `PLANNED` | Centimeter-level positioning for haul road geofencing, blind curve warning, and dump-crest approach. Wire schema contains latitude/longitude fields. | Dual-antenna RTK GNSS module integration via UART. |

### 2.3 Edge Intelligence & Risk Engine

| Subsystem / Feature | Current Status | Description & Engineering Evidence | Next Milestone |
| :--- | :--- | :--- | :--- |
| **Embedded Collision Risk Engine** | `IMPLEMENTED` | Deterministic Time-to-Collision (TTC) algorithm, dynamic deceleration thresholding, and proximity risk levels (`NORMAL`, `CAUTION`, `WARNING`, `CRITICAL`). | Kalmar-filter based velocity estimation from range deltas. |
| **Hazard State Memory & Decay** | `IMPLEMENTED` | Temporal hazard holding register that maintains active warning state for a defined grace period before decaying, preventing warning flicker during packet jitter. | Exponential decay weighting based on vehicle speed. |
| **Fail-Safe Fallback Manager** | `IMPLEMENTED` | Heartbeat watchdog detecting peer silence (`TIMEOUT_SILENCE_MS = 2500ms`). Automatically transitions to autonomous local-only sensing on link loss. | Safe degraded-mode audio-visual operator chime. |
| **DAAS-V2V ML Adaptive Engine** | `IMPLEMENTED (BENCH/SIM)` | Python-based XGBoost pipeline predicting channel congestion (`CONGESTED`/`UNCONGESTED`), traffic density (`LOW`/`MED`/`HIGH`), and optimal beaconing rate (2–20 Hz). | Quantization to TensorFlow Lite Micro for on-node ESP32 execution. |
| **ML Inference Edge Execution** | `PLANNED` | Running 8-bit quantized decision tree or neural model directly on ESP32 Tensilica dual-core. (Currently, ML executes host-side via serial telemetry bridge). | PlatformIO embedded TFLite Micro runtime build. |

### 2.4 Human-Machine Interface (HMI) & Telemetry

| Subsystem / Feature | Current Status | Description & Engineering Evidence | Next Milestone |
| :--- | :--- | :--- | :--- |
| **SSD1306 0.96" I2C OLED** | `PROTOTYPE/EXPERIMENTAL` | Local cockpit display showing system state, peer distance, risk level, TTC, and packet health. | High-brightness, IP67 sunlight-readable in-cab display. |
| **Audio-Visual Warning Cues** | `PROTOTYPE/EXPERIMENTAL` | Active piezo buzzer with variable pulse cadence (1 Hz caution, 4 Hz warning, continuous critical) and dual red/green status LEDs. | 85 dBA rugged in-cab industrial sounder. |
| **Serial Telemetry Streaming** | `IMPLEMENTED` | Real-time JSON-formatted telemetry streamed over USB UART at 115200 baud for gateway ingestion, dashboard plotting, and model training. | Binary COBS-encoded stream for high-throughput bandwidth savings. |
| **Web Guidance Console** | `PROTOTYPE/EXPERIMENTAL` | HTML5/React-based telemetry visualizer showing vehicle states, synthetic map, and live sensor graphs. | Integration with open-pit dispatch server (FMS). |

---

## 3. Explicit Negative Verification Register ("What Has NOT Been Done")

To protect research credibility and eliminate ambiguity during evaluation:

1. **NO Open-Cast Mine Field Trials:**  
   The system has **never been deployed or field-tested** in an active NMDC iron ore mine (e.g. Kirandul, Bailadila, Donimalai) or any other commercial quarry. All physical measurements derive from indoor laboratory bench testing.
2. **NO Heavy Mining Machinery Installation:**  
   The prototype hardware has **never been installed** on a 100T/240T CAT/Komatsu/BEML dump truck, electric shovel, excavator, or surface water bowser.
3. **NO Production Dust/Fog Chamber Certification:**  
   The system has not undergone ISO 12188 or EN 50419 industrial environmental testing for high-density suspended iron ore particulate or humidity saturation.
4. **NO Real mmWave Radar or Thermal Sensor Interfacing:**  
   All current proximity telemetry originates from HC-SR04 ultrasonic pulses and synthetic datasets. mmWave radar and thermal camera integration are strictly architectural designs and future scale-up modules.
5. **NO DSRC/C-V2X Band Approval:**  
   RF testing has been restricted to unlicensed 2.4 GHz ISM spectrum using ESP-NOW. No 5.9 GHz ITS band licenses or homologations have been sought or granted.
