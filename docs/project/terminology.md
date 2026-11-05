# Terminology & Standardized Glossary

**Project:** DAAS-V2V / SIH26007 Mine Vehicle Safety System  
**Document Type:** Technical Lexicon & Domain Taxonomy  

---

## 1. Domain Terms & Acronyms

| Term / Acronym | Full Form | Definition & Engineering Context |
| :--- | :--- | :--- |
| **V2V** | Vehicle-to-Vehicle | Direct, wireless, ad-hoc communication between mobile vehicles without reliance on cellular towers or roadside base stations. |
| **V2X** | Vehicle-to-Everything | Umbrella term encompassing V2V, Vehicle-to-Infrastructure (V2I), Vehicle-to-Pedestrian (V2P), and Vehicle-to-Network (V2N). |
| **OBU** | On-Board Unit | Hardware computing, transceiver, and interface terminal permanently installed inside a vehicle cabin or electrical bay. |
| **RSU** | Roadside Unit | Fixed stationary transceiver positioned along haul road intersections, blind corners, or dump yards to relay alerts and provide telemetry. |
| **TTC** | Time-to-Collision | The calculated time remaining before two vehicles or an obstacle collide, assuming current relative distance and closing velocity remain constant: $TTC = \frac{d}{v_{rel}}$. |
| **DGMS** | Directorate General of Mines Safety | The Indian regulatory agency under the Ministry of Labour and Employment governing safety regulations, standards, and equipment approvals in Indian mines. |
| **NMDC** | NMDC Limited | Formerly National Mineral Development Corporation; India's largest iron ore producer under the Ministry of Steel and problem statement sponsor for SIH26007. |
| **ESP-NOW** | ESP-NOW Protocol | A low-power, connectionless, proprietary 2.4 GHz communication protocol developed by Espressif Systems utilizing IEEE 802.11 vendor-specific action frames. |
| **DAAS** | Density-Aware Adaptive Secure | The supervisory machine learning architecture designed to dynamically estimate network traffic density and adapt broadcast frequencies. |
| **C-V2X** | Cellular Vehicle-to-Everything | 3GPP standard (Release 14/15/16) enabling direct device-to-device sidelink communication (PC5 interface) on 5.9 GHz ITS spectrum. |
| **DSRC** | Dedicated Short-Range Communications | IEEE 802.11p-based wireless communication standard for automotive safety applications. |
| **CSMA/CA** | Carrier-Sense Multiple Access with Collision Avoidance | MAC layer protocol where nodes listen to the channel before transmitting to avoid RF packet collisions. |
| **HMI** | Human-Machine Interface | The visual and auditory cockpit interface (OLED display, buzzer, LEDs) delivering actionable safety warnings to the machine operator. |

---

## 2. Core Architectural Concepts

### Safety-Path Isolation
A deterministic architectural rule requiring that life-critical hazard and emergency braking packets bypass all software queues, rate limiters, and machine learning adaptation logic. Emergency packets are scheduled with immediate hardware transmission preemption, ensuring that an algorithm crash or network throttle can never delay an emergency stop warning.

### Hazard Memory & Temporal Decay
An algorithmic state holding mechanism implemented in embedded firmware. When an emergency hazard flag (such as hard braking) is received, the receiver latches the hazard state and holds the visual/audible alert for a fixed duration (e.g., 1500 ms) before decaying, even if intermittent RF packet loss occurs. This eliminates rapid "warning flicker" that confuses drivers.

### Fail-Safe Fallback (Autonomous Degraded Mode)
A deterministic watchdog state machine. If no valid V2V beacon is received from a peer node within a defined timeout threshold (e.g. 2500 ms), the node formally declares the V2V link lost. It warns the operator via an HMI chime and falls back exclusively to local autonomous sensors (ultrasonic/radar).

### Message Freshness & Sequence Validation
Every wire packet carries a sender-stamped monotonic sequence counter and transmission timestamp. The receiver checks that incoming packet sequence numbers are monotonically increasing (detecting dropped packets or replays) and computes message age relative to the local monotonic clock to discard stale, delayed packets.

---

## 3. Mining-Specific Operations & Hazards

| Mining Term | Meaning in Open-Cast Iron Ore Context |
| :--- | :--- |
| **Open-Cast Mine** | Surface mining excavation where ore extraction occurs from open pits using successive terraced steps (benches). |
| **Haul Road** | Unpaved, graded internal roadway connecting the mining excavation pit to processing plants, stockyards, and waste dumps, typically with gradients between 1:16 and 1:10. |
| **Haul Dumper** | Massive off-highway dump truck (typically 35-ton to 240-ton payload capacity) used for transporting blasted rock and iron ore. |
| **Bench** | A horizontal shelf or terrace excavated into the mine pit wall, creating vertical drop-off edges that present severe rollover hazards. |
| **Radiation Fog** | Dense, ground-level winter fog common in deep open-pit excavations due to nocturnal radiative cooling, trapping moisture and dust near the pit floor. |
| **Hematite Dust** | Fine, airborne iron oxide particulate generated by heavy drilling, blasting, and dumper transit that drastically reduces optical visibility and causes light back-scattering. |
| **Dump Crest** | The outer edge of a waste dump or crusher hopper where dump trucks reverse to unload; zero visibility here carries catastrophic fall-from-height risks. |
