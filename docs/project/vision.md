# System Vision & Strategic Architecture

**System Name:** DAAS-V2V / Cooperative FogSafe Fleet Intelligence  
**Problem Statement:** SIH26007 — "Safe and Efficient Operation of Mine Vehicles in Fog and Low-Visibility Conditions in Open Cast Iron Ore Mines"  
**Target Organization:** NMDC Limited / Ministry of Steel, Government of India  
**Development Team:** Team IGRIS07 (Team ID: 137940), SKP Engineering College  

---

## 1. Executive Summary

In open-cast iron ore mining, severe environmental visibility degradation—caused by dense winter radiation fog, continuous airborne silica/hematite dust clouds from drilling and dumping, and blinding torrential monsoon rainfall—frequently reduces driver line-of-sight to less than 5 meters. 

Simultaneously, massive haul trucks (such as 100-ton to 240-ton ultra-class dumpers) possess enormous mechanical momentum and extensive geometric blind spots extending up to 15 meters around the vehicle chassis. When drivers cannot see preceding machinery or stationary obstacles, mines are forced into costly operational standstills, or worse, catastrophic rear-end, head-on, or bench-edge rollover collisions.

The **DAAS-V2V (Density-Aware Adaptive Secure Vehicle-to-Vehicle) Mine Intelligence Architecture** is a cooperative cyber-physical safety system designed to maintain zero-fatality haulage productivity under zero-visibility operating conditions.

```
+-----------------------------------------------------------------------------------+
|                            COOPERATIVE VEHICLE FLEET                              |
|                                                                                   |
|   +--------------------------+                  +--------------------------+      |
|   |  Haul Dumper A (Leader)  |                  | Haul Dumper B (Follower) |      |
|   |   - Heavy braking event  |                  |   - High-speed approach  |      |
|   |   - Zero cabin visibility|  ESP-NOW / C-V2X |   - Obscured blind road  |      |
|   |                          | === Broadcast == |                          |      |
|   |   [ Emergency Frame ]    | =======> (50m+)  |   [ Cockpit HMI Warning] |      |
|   +--------------------------+                  +--------------------------+      |
|                 |                                             |                   |
+-----------------|---------------------------------------------|-------------------+
                  v                                             v
      +-----------------------------------------------------------------+
      |                 EDGE SAFETY & RISK ENGINE                       |
      |   1. Instantaneous Safety-Path Preemption (<5 ms)               |
      |   2. Deterministic Time-to-Collision (TTC) Calculation          |
      |   3. Hazard Memory Temporal Holding (Anti-Flicker)              |
      |   4. Autonomous Fallback on Radio Link Loss (Degraded Mode)     |
      +-----------------------------------------------------------------+
                                       |
                                       v
      +-----------------------------------------------------------------+
      |             SUPERVISORY ML CONGESTION INTELLIGENCE              |
      |   - Channel Density & Packet Contention Prediction              |
      |   - Dynamic Beacon Rate Adaptation (2 Hz to 20 Hz)              |
      |   - Real-Time Telemetry Streaming to Mine Operations Base       |
      +-----------------------------------------------------------------+
```

---

## 2. Core Pillars of the Architecture

### 2.1 Cooperative Electronic Line of Sight (Virtual Vision)
Unlike optical cameras and human vision, which suffer total extinction in dense fog and dust aerosols, radio frequency (RF) signals penetrate particulate clouds unimpeded. By continuously sharing position, velocity, braking telemetry, and hazard alerts between peer vehicles via low-latency direct V2V links, each driver gains an "electronic windshield" that reveals preceding vehicles up to hundreds of meters before physical optical acquisition.

### 2.2 Strict Safety-Path Isolation
The architecture establishes a non-negotiable wall between machine learning optimization and life-critical emergency broadcasting:
- **Safety Critical Channel:** Emergency brake warnings, sudden deceleration flags, and impending collision alerts transmit on an unthrottled, prioritized hardware path with zero queuing delay.
- **ML Optimization Channel:** Adaptive rate control, channel density estimation, and network telemetry adaptation are strictly confined to routine periodic beacons. An ML model failure or host gateway crash can **never** suppress an emergency hazard alert.

### 2.3 Deterministic Fail-Safe Fallback
Mining haul roads are harsh electromagnetic environments characterized by steep pit-wall reflections, deep bench occlusion, and high iron ore RF attenuation. If V2V radio contact is broken, the vehicle node automatically detects peer silence within 2.5 seconds, triggers an in-cab chime, and falls back to local autonomous perception (ultrasonic/radar) to prevent silent safety failures.

### 2.4 Research Lineage to Industrial Deployment
This repository represents an authentic, step-by-step engineering progression:
1. **Phase 1 (Legacy):** Point-to-point wireless transmission experiments using CC2500 transceivers.
2. **Phase 2 (DAAS-V2V ML):** High-density network simulation, congestion modeling, and telemetry infrastructure validated on 85,248 synthetic VANET records.
3. **Phase 3 (SIH26007 Prototype):** Dual-node ESP32 physical bench prototype with hardware HMI, ultrasonic ranging surrogate, brake switch telemetry, deterministic risk engine, and fallback watchdog.
4. **Phase 4 (Industrial Roadmap):** DGMS-compliant ruggedized On-Board Units (OBU), 77 GHz mmWave radar fusion, uncooled LWIR thermal vision, and dual-antenna RTK GNSS for commercial open-cast mine deployment.
