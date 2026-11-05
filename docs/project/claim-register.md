# Research & Engineering Claim Register

**Project:** DAAS-V2V / SIH26007 Mine Safety System  
**Maintained By:** Team IGRIS07, SKP Engineering College  
**Authority:** Technical Architecture & Research Integrity Registry  
**Branch:** `feature/repository-reengineering`

---

## 1. Principles of Claim Verification

Every scientific claim, benchmark result, and capability statement made in this repository must map to:
1. **Source of Truth:** The specific code, file, or physical test session where the data was gathered.
2. **Environment & Modality:** Synthetic simulation, host PC Python execution, microcontroller bench hardware, or planned specification.
3. **Hardware Boundaries:** The exact silicon, sensors, and transceivers utilized.
4. **Explicit Limitations:** Boundary conditions where the claim does not apply.

Any claim found without corresponding data or bench logs is categorized as `UNVERIFIED` and barred from technical evaluations.

---

## 2. Claim Master Register

| ID | Claim Statement | Claim Category | Environment & Source of Truth | Hardware / Framework | Limitations & Boundary Conditions |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CLM-01** | *Machine learning model achieves 99.72% test accuracy in traffic density classification.* | `ML Simulation Metric` | `ml/data/synthetic_vanet.csv`<br>`ml/evaluation/DAAS_FINAL_ML_VALIDATION.md`<br>`ml/scripts/train_all.py` | Python 3.11, XGBoost Classifier, Intel/AMD Host CPU | **Strictly synthetic data.** Evaluated on 85,248 synthetic VANET records generated via mathematical simulation. **Does not represent real mine haul truck fleet data.** |
| **CLM-02** | *Model achieves 0.9301 ROC-AUC score for network congestion prediction.* | `ML Simulation Metric` | `ml/data/synthetic_vanet.csv`<br>`ml/models/congestion_model.json` | Python 3.11, XGBoost binary classification | Simulated packet collisions and vehicle densities. Not validated on real IEEE 802.11p or 3GPP C-V2X radios. |
| **CLM-03** | *Average ML model inference latency is 9.93 ms.* | `ML Benchmark` | `ml/evaluation/ml_validation_audit.json` | Host Workstation Python runtime (scikit-learn / XGBoost C-API) | **Measured on host PC CPU**, not on the ESP32 microcontroller. Embedded inference requires model quantization. |
| **CLM-04** | *Wireless communication operates reliably across 50 meters line-of-sight.* | `RF Bench Prototype` | `firmware/vehicle-node/`<br>`hardware/photos/bench-test.jpg` | 2x ESP32-WROOM-32, ESP-NOW 2.4 GHz (802.11 action frames), 0 dBm internal PCB trace antenna | Measured in indoor campus corridor line-of-sight. Subject to RF multipath degradation, dust scattering, and metal shielding from heavy mining dump bodies. |
| **CLM-05** | *One-way wireless message transmission latency is under 5 ms.* | `Embedded Prototype` | ESP-NOW physical packet delivery bench benchmarks | ESP-NOW 250-byte payload at 1 Mbps PHY rate | Excludes host serial logging delays. Assumes clear 2.4 GHz channel without severe Wi-Fi co-channel interference. |
| **CLM-06** | *Obstacle distance is detected up to 4.0 meters with centimeter resolution.* | `Sensor Prototype` | `firmware/vehicle-node/src/sensor_manager.cpp`<br>`hardware/photos/sensor-assembly.jpg` | HC-SR04 Ultrasonic Transducer (40 kHz acoustic ping) | Acoustic waves fail in high-speed wind, heavy dust saturation, and industrial machinery acoustic noise (>110 dBA). **Surrogate sensor only**; not suitable for production open-cast mines. |
| **CLM-07** | *Safety-critical emergency brake messages bypass ML throttling with zero queue delay.* | `Safety Architecture` | `firmware/common/safety/safety_isolation.h`<br>`firmware/vehicle-node/src/priority_engine.cpp` | C++ firmware logic, FreeRTOS queue preemption | Guaranteed in software priority logic. Hardware PHY transmission is still subject to CSMA/CA channel contention. |
| **CLM-08** | *Autonomous fail-safe fallback activates within 2.5 seconds of communication loss.* | `Fault Tolerance` | `firmware/vehicle-node/src/fallback_manager.cpp` | Deterministic millisecond timer watchdog | Tested on dual-node testbench by physically disconnecting receiver power. Displays visual/audible alert and relies on local ultrasonic sensor. |
| **CLM-09** | *Vehicle hazard memory holds active danger status for 1500 ms to eliminate alert flicker.* | `Temporal Stability` | `firmware/vehicle-node/src/hazard_state.cpp` | Monotonic software holding timer | Bench validated by simulating intermittent packet dropouts during active hazard state. |
| **CLM-10** | *Cooperative collision prevention in zero-visibility open-cast mine environments.* | `System Operational Vision` | `docs/problem-statement/SIH26007.md`<br>`research/papers/IConSCEPT2026_DAAS_V2V_Mine_IEEE_Draft.tex` | Conceptual system architecture combining V2V, mmWave radar, and thermal imaging | **PLANNED / NOT VALIDATED IN PRODUCTION MINES.** Evaluated in hardware-in-the-loop and scale-model bench tests. Field validation in NMDC mines is an upcoming milestone. |

---

## 3. Disallowed and Corrected Overclaims

The following historical claims or common hackathon exaggerations are formally repudiated and corrected:

| Previously Ambiguous / Overstated Claim | Correction & True Engineering Fact |
| :--- | :--- |
| *"AI runs inside the vehicle chip preventing accidents in real mines"* | **Correction:** The current hardware prototype runs deterministic C++ collision logic on an ESP32. The ML pipeline runs on a host server/laptop ingesting serial telemetry from the ESP32. Mine deployment is planned. |
| *"99.7% collision prevention rate in fog"* | **Correction:** The 99.72% figure represents **machine learning density classification accuracy** on a synthetic benchmark dataset, NOT a real-world vehicle crash prevention rate. |
| *"System uses radar and thermal vision for zero visibility"* | **Correction:** Radar and thermal cameras are specified in the production architectural design; the current bench prototype uses an HC-SR04 ultrasonic sensor as a functional low-cost surrogate. |
| *"Compliant with IEEE 802.11p and 3GPP Release 16"* | **Correction:** The prototype uses proprietary ESP-NOW action frames over standard 2.4 GHz Wi-Fi hardware. Standards compliance is an architectural roadmap target for industrial OBU hardware. |

---

## 4. Verification Check Procedure

When verifying this repository:
1. Run `python -m pytest ml/tests/` to verify ML pipeline, schemas, and policy guarantees.
2. Compile and execute `firmware/tests/` to verify packet validation, CRC16, and risk engine logic.
3. Review `media/prototype/` to inspect the exact physical dual-ESP32 breadboard prototype.
4. Cross-check all presentation slides and papers against this Claim Register before external publication.
