# End-to-End Data Flow Architecture

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet System  
**Document Type:** System Data Flow & Interface Architecture  

---

## 1. Complete End-to-End Data Flow Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                 PHYSICAL VEHICLE NODE 1 (TRANSMITTER)                             |
+---------------------------------------------------------------------------------------------------+
|  [ Ultrasonic Echo Pulse ] -> GPIO 18 -> pulseIn() -> Median Filter -> distance_m                 |
|  [ Tactile Push Button   ] -> GPIO 19 -> digitalRead() -> Debounce -> brake_active                |
|                                                                                                   |
|  [ Priority Engine ] -------------------------------------------------------------+               |
|    - Is emergency brake active?                                                   |               |
|    - YES: Preempt schedule, Priority = 0x00, Emergency Burst                      |               |
|    - NO:  Wait for adaptive interval (e.g. 100ms), Priority = 0x03                |               |
|                                                                                   |               |
|  [ Serialization & CRC16 Signing ] <----------------------------------------------+               |
|    - v2v_packet_t { magic:0xD4, ver:2, prio, sender:1, seq++, dist, spd, crc16 }                  |
|                                                                                                   |
|  [ ESP-NOW Physical Driver ] -> 2.4 GHz 802.11 Vendor Action Frame -> PCB Antenna                 |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v  (ESP-NOW 2.4 GHz Air Interface, <5ms)
+---------------------------------------------------------------------------------------------------+
|                                  PHYSICAL VEHICLE NODE 2 (RECEIVER)                               |
+---------------------------------------------------------------------------------------------------+
|  [ PCB Antenna ] -> ESP32 Wi-Fi MAC Layer Interrupt -> onDataRecv() Callback                     |
|                                                                                                   |
|  [ Integrity & Sanity Gate ]                                                                      |
|    - Validate Magic (0xD4), Version (0x02), CRC16 Checksum, Sequence Continuity, Freshness (<500ms)|
|                                                                                                   |
|  [ Subsystem Updates ]                                                                            |
|    1. FallbackManager.recordPeerHeartbeat() -> Resets 2.5s watchdog timer                         |
|    2. HazardStateManager.triggerHazard() -> Latches active hazard for 1500ms                      |
|    3. RiskEngine.evaluate() -> Computes TTC = d / v_rel, classifies RISK_LEVEL                    |
|                                                                                                   |
|  [ Cockpit HMI Actuation ]                                                                        |
|    - SSD1306 OLED: Renders live distance, speed, TTC, and operational status                     |
|    - Piezo Buzzer: Triggers audible cadences (Silent / 1 Hz chirp / 4 Hz pulse / Continuous)     |
|    - Status LEDs: Drives Green (Safe) and Red (Danger) indicator lamps                            |
|                                                                                                   |
|  [ Serial Telemetry Streamer ] -> Streams JSON line at 115200 baud over USB UART                  |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v  (USB UART Serial Stream, 115200 Baud)
+---------------------------------------------------------------------------------------------------+
|                                  HOST GATEWAY & DAAS-V2V ML SERVER                                |
+---------------------------------------------------------------------------------------------------+
|  [ tools/telemetry/esp32_gateway.py ]                                                             |
|    - Ingests and parses raw JSON telemetry lines                                                  |
|    - Logs real-time metrics to SQLite / PostgreSQL database                                       |
|                                                                                                   |
|  [ ml/src/daas/features/pipeline.py ]                                                             |
|    - Computes rolling network features: PDR, Packet Drop Rate, Rolling RSSI, Density proxy        |
|                                                                                                   |
|  [ ml/src/daas/inference/engine.py ]                                                              |
|    - Evaluates XGBoost Congestion Classifier (ROC-AUC 0.9301)                                     |
|    - Evaluates XGBoost Density Classifier (99.72% Accuracy)                                       |
|                                                                                                   |
|  [ ml/src/daas/policy/adaptive.py ]                                                               |
|    - Generates target beacon transmission rate (2 Hz to 20 Hz)                                    |
|    - Sends adaptation feedback command over Serial to Node: {"rate": 15.0}                        |
|                                                                                                   |
|  [ Web Guidance Console ]                                                                         |
|    - Displays real-time vehicle positions, safety heatmaps, and haul road risk metrics            |
+---------------------------------------------------------------------------------------------------+
```
