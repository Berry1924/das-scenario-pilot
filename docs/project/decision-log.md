# Architectural Decision Records (ADR)

**Project:** DAAS-V2V / SIH26007 Mine Safety System  
**Document Type:** Formal Decision Log  
**Repository Branch:** `feature/repository-reengineering`

---

## Index of Decisions

- [ADR-001: ESP-NOW Protocol Selection for Physical Bench Prototype](#adr-001-esp-now-protocol-selection-for-physical-bench-prototype)
- [ADR-002: HC-SR04 Ultrasonic Transducer as Proximity Sensing Surrogate](#adr-002-hc-sr04-ultrasonic-transducer-as-proximity-sensing-surrogate)
- [ADR-003: Strict Safety-Path Isolation for Life-Critical Packets](#adr-003-strict-safety-path-isolation-for-life-critical-packets)
- [ADR-004: Host-Side ML Execution with Telemetry Ingestion Bridge](#adr-004-host-side-ml-execution-with-telemetry-ingestion-bridge)
- [ADR-005: Resolution of GPIO 4 Hardware Pin Allocation Conflict](#adr-005-resolution-of-gpio-4-hardware-pin-allocation-conflict)
- [ADR-006: Protocol Integrity with Wire-Level CRC16 and Sequence Tracking](#adr-006-protocol-integrity-with-wire-level-crc16-and-sequence-tracking)

---

### ADR-001: ESP-NOW Protocol Selection for Physical Bench Prototype
* **Status:** Accepted & Implemented  
* **Context:** The project requires a fast, connectionless, peer-to-peer radio frequency link between mobile vehicle nodes. Standard Wi-Fi infrastructure mode requires an Access Point (AP) and introduces 2–5 second DHCP/handshake latency. Bluetooth Low Energy (BLE) requires pairing and is subject to slow connection intervals (7.5–30 ms) with high connection-drop overhead.
* **Decision:** Utilize Espressif ESP-NOW protocol over 2.4 GHz IEEE 802.11 vendor-specific action frames.
* **Consequences:**
  - *Positive:* Sub-5 ms packet delivery latency; zero connection pairing delay; low frame overhead (250-byte maximum payload); native support on low-cost ESP32-WROOM-32 hardware.
  - *Negative:* Restricted to 2.4 GHz ISM band (co-channel Wi-Fi interference); limited to 20 paired peers in unicast; bench prototype only (not compliant with 5.9 GHz C-V2X/DSRC automotive standards).

---

### ADR-002: HC-SR04 Ultrasonic Transducer as Proximity Sensing Surrogate
* **Status:** Accepted & Implemented (Bench Prototype Only)  
* **Context:** High-end industrial 77 GHz mmWave radar sensors (e.g. TI AWR1843, Continental ARS408) cost upwards of $300–$1,500 each and require high-speed SPI/CAN bus parsing. For university laboratory bench evaluation and algorithmic verification of collision risk logic, an immediate, functional distance measurement module was required.
* **Decision:** Employ the HC-SR04 ultrasonic sensor (40 kHz acoustic transducer) to measure obstacle distance up to 4.0 meters on the physical bench.
* **Consequences:**
  - *Positive:* Provides immediate, deterministic distance measurements ($0.05\text{ m} \le d \le 4.0\text{ m}$) enabling complete end-to-end hardware-in-the-loop testing of the embedded risk engine, OLED HMI, and telemetry streaming.
  - *Explicit Limitation:* Acoustic waves are severely degraded by open-cast mine environmental conditions (heavy wind shear, suspended dust scattering, acoustic noise >110 dBA from heavy diesel engines). The HC-SR04 is **strictly an accessible bench surrogate**, with mmWave radar planned for industrial scale-up.

---

### ADR-003: Strict Safety-Path Isolation for Life-Critical Packets
* **Status:** Accepted & Implemented  
* **Context:** The DAAS supervisory architecture includes machine learning models that dynamically adapt transmission rates (2 Hz to 20 Hz) based on estimated RF channel congestion. If an emergency brake event occurs, feeding the emergency alert through the ML rate limiter or waiting for an inference cycle could introduce dangerous transmission delays or suppress the warning entirely during CPU thrashing.
* **Decision:** Establish an uncrossable architectural wall ("Safety-Path Isolation"). Emergency brake flags and imminent collision alerts (`PRIORITY_EMERGENCY = 0x00`) bypass all software queuing, adaptive rate throttling, and ML decision loops, preemptively triggering immediate PHY transmission.
* **Consequences:**
  - *Positive:* Deterministic, zero-queue emergency broadcast latency (<5 ms); safety guarantees remain mathematically independent of ML model state or software crashes.
  - *Negative:* Brief RF channel burst during multi-vehicle simultaneous emergency events, requiring future channel reservation protocols at scale.

---

### ADR-004: Host-Side ML Execution with Telemetry Ingestion Bridge
* **Status:** Accepted & Implemented  
* **Context:** The DAAS-V2V ML intelligence engine comprises XGBoost classifiers trained on 85,248 multi-feature synthetic records to predict channel congestion and vehicle density. Direct on-chip execution on the ESP32 would require heavy quantization, memory footprint management, and would preclude real-time feature auditing and visual dashboarding during laboratory demonstrations.
* **Decision:** Run the full XGBoost and FastAPI ingestion pipeline on a host computer/server, ingesting structured serial telemetry streamed from the ESP32 node via USB UART at 115200 baud.
* **Consequences:**
  - *Positive:* Enables full explainability (SHAP values), multi-model ensemble evaluation, high-resolution telemetry logging, and rapid hyperparameter tuning without microcontroller flashing cycles.
  - *Negative:* Introduces serial bridge latency (~10–15 ms); leaves on-chip micro-ML (TensorFlow Lite Micro / TinyEngine) as an open roadmap milestone for Phase 4.

---

### ADR-005: Resolution of GPIO 4 Hardware Pin Allocation Conflict
* **Status:** Accepted & Resolved  
* **Context:** Code review of the legacy codebase revealed a critical pin allocation collision in `daas_v1.ino`: `BRAKE_PIN` was defined as GPIO 4 (`#define BRAKE_PIN 4`) and `LED_DANGER_PIN` was simultaneously defined as GPIO 4 (`#define LED_DANGER_PIN 4`). In `daas_v2.ino`, `BRAKE_PIN` was moved to GPIO 19, but no documentation existed explaining the change.
* **Decision:** Formalize the pin mapping standard:
  - **GPIO 19:** Dedicated digital input with internal pull-up resistor for `BRAKE_SWITCH_PIN`.
  - **GPIO 4:** Dedicated digital output for `LED_DANGER_PIN` (Red Warning LED).
* **Consequences:**
  - *Positive:* Eliminates electrical and logical contention between active-low push button and LED driver; prevents hardware malfunction during emergency brake actuation.

---

### ADR-006: Protocol Integrity with Wire-Level CRC16 and Sequence Tracking
* **Status:** Accepted & Implemented  
* **Context:** While the underlying 802.11 MAC layer provides a 32-bit Frame Check Sequence (FCS), memory corruption within the ESP-NOW software buffer or UART streaming bridge can inject corrupted bytes into the risk engine. Additionally, detecting packet loss and channel congestion requires tracking dropped frames.
* **Decision:** Define a custom packed wire-format structure (`v2v_packet_t`) featuring:
  1. Magic synchronization byte `0xD4`.
  2. Monotonic 32-bit sender sequence counter (`seq_num`).
  3. Sender monotonic millisecond timestamp (`timestamp_ms`).
  4. CRC16-CCITT payload checksum computed across all payload fields.
* **Consequences:**
  - *Positive:* Corrupted packets are rejected before reaching the risk decision pipeline; receivers can calculate exact message age, sequence gaps, and packet drop percentages in real time.
  - *Negative:* Adds 8 bytes of protocol overhead per transmission frame.
