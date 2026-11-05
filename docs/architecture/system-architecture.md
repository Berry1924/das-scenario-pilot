# System Architecture & Layered Decomposition

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet System  
**Document Type:** High-Level Architecture Specification  

---

## 1. High-Level System Architecture

The DAAS-V2V / SIH26007 system operates across three tightly coupled tiers:
1. **Physical On-Board Vehicle Nodes (Edge Tier):** Microcontroller hardware performing real-time sensor sampling, low-latency ad-hoc V2V communication, deterministic risk calculations, and cockpit HMI delivery.
2. **Host Gateway & Telemetry Bridge (Edge Gateway Tier):** USB UART bridge ingesting structured JSON telemetry from vehicle nodes, running the DAAS machine learning engine for network state estimation.
3. **Mine Operations Fleet Dispatch (Enterprise Tier):** Central fleet management server monitoring vehicle safety metrics, congestion heatmaps, and haul road alerts across the open-cast mine.

```
+===================================================================================+
|                          OPEN-CAST MINE OPERATIONAL SPACE                         |
+===================================================================================+
|                                                                                   |
|   +----------------------------+                 +----------------------------+   |
|   |   VEHICLE NODE 1 (LEAD)    |                 |  VEHICLE NODE 2 (FOLLOWER) |   |
|   |  - ESP32 Dual Core Tensilica  - ESP-NOW 2.4GHz - ESP32 Dual Core Tensilica|   |
|   |  - HC-SR04 Ultrasonic      |<=== Ad-Hoc ===>|  - HC-SR04 Ultrasonic      |   |
|   |  - Emergency Brake Switch  |   (Direct P2P)  |  - Emergency Brake Switch  |   |
|   |  - SSD1306 Cockpit OLED    |                 |  - SSD1306 Cockpit OLED    |   |
|   |  - Audio-Visual Buzzer/LED |                 |  - Audio-Visual Buzzer/LED |   |
|   +----------------------------+                 +----------------------------+   |
|                 |                                              |                  |
+=================|==============================================|==================+
                  | USB UART Stream                              | USB UART Stream  |
                  v (115200 Baud)                                v (115200 Baud)    |
+===================================================================================+
|                  HOST GATEWAY & DAAS-V2V ML INTELLIGENCE TIER                     |
+===================================================================================+
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   |                   TELEMETRY INGESTION & PIPELINE (FastAPI)                |   |
|   |   - Serial Frame Parsing & Validation                                     |   |
|   |   - Feature Engineering (Rolling RSSI, Packet Delivery Ratio, Dynamics)   |   |
|   +---------------------------------------------------------------------------+   |
|                                       |                                           |
|                                       v                                           |
|   +---------------------------------------------------------------------------+   |
|   |                 SUPERVISORY MACHINE LEARNING ENGINES                      |   |
|   |   - Congestion Predictor (XGBoost Binary Classifier, ROC-AUC 0.9301)       |   |
|   |   - Density Estimator (XGBoost Multi-Class, 99.72% Accuracy)              |   |
|   |   - Adaptive Rate Controller (Dynamically adjusts beacons: 2Hz to 20Hz)   |   |
|   +---------------------------------------------------------------------------+   |
|                                       |                                           |
+=======================================|===========================================+
                                        v REST / WebSockets
+===================================================================================+
|                    MINE OPERATIONS & DISPATCH CONSOLE TIER                        |
+===================================================================================+
|   - Real-Time Haul Road Fleet Tracking Dashboard                                  |
|   - Driver Collision Hazard & Berm Breach Alarm Logging                           |
|   - Historical Incident Reconstruction & Telemetry Database (SQLite / Postgres)   |
+===================================================================================+
```

---

## 2. Core Functional Layers

### Layer 1: Physical Perception & Actuation
- **Sensors:** Near-field ultrasonic distance transducer (bench surrogate) and active-low tactile brake switch. (Planned: 77 GHz mmWave radar, uncooled LWIR thermal vision).
- **Actuators:** SSD1306 0.96" graphic OLED screen, active piezo buzzer, high-intensity red/green warning LEDs.

### Layer 2: Real-Time Protocol & Safety Preemption
- **Direct P2P Link:** ESP-NOW 2.4 GHz action frames delivering sub-5ms latency across 50m line-of-sight.
- **Safety-Path Preemption:** Life-critical emergency braking packets bypass all software queues and transmit immediately.

### Layer 3: Edge Decision & Risk Engine
- Deterministic Time-to-Collision (TTC) calculations based on distance and closing speed.
- Temporal hazard holding memory (1500 ms) preventing warning flicker during packet jitter.
- Watchdog timer transitioning to autonomous fallback within 2.5 seconds upon peer silence.

### Layer 4: Supervisory Network Intelligence (DAAS-V2V)
- Machine learning models predicting network congestion and traffic density from RF metrics.
- Closed-loop rate feedback returning optimal transmission frequencies to the vehicle node.
