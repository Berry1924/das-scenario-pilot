# System Architecture Diagrams (Mermaid Reference)

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Safety System  
**Document Type:** Visual Systems Architecture Specification  

---

## 1. Multi-Tier System Architecture

```mermaid
flowchart TD
    subgraph EdgeTier["Physical Edge Tier (Mining Vehicle Nodes)"]
        subgraph Node1["Vehicle Node 1 (Lead Dumper)"]
            N1_Brake["Brake Switch (GPIO 19)"]
            N1_ESP["ESP32 Microcontroller"]
            N1_LED["Status LEDs (GPIO 2, 4)"]
        end
        subgraph Node2["Vehicle Node 2 (Follower Dumper)"]
            N2_US["HC-SR04 Ultrasonic"]
            N2_ESP["ESP32 Microcontroller"]
            N2_OLED["SSD1306 OLED (I2C)"]
            N2_Buzzer["Piezo Buzzer (GPIO 13)"]
        end
        Node1 <== "ESP-NOW 2.4 GHz (<5 ms)" ==> Node2
    end

    subgraph GatewayTier["Host Gateway & ML Intelligence Tier"]
        GW["Serial Bridge Gateway (esp32_gateway.py)"]
        Pipe["Feature Pipeline (PDR, RSSI, Dynamics)"]
        ML_Cong["XGBoost Congestion Model (ROC-AUC 0.9301)"]
        ML_Dens["XGBoost Density Model (99.72% Acc)"]
        Pol["Adaptive Rate Policy (2 Hz to 20 Hz)"]
        GW --> Pipe --> ML_Cong & ML_Dens --> Pol
        Pol -. "Rate Command over Serial" .-> Node1
    end

    subgraph OpsTier["Mine Operations & Dispatch Tier"]
        DB[(Telemetry Database)]
        Dash["Mine Dispatch Guidance Console"]
        GW --> DB
        GW --> Dash
    end

    Node1 -->|"USB Serial JSON (115200)"| GW
```

---

## 2. Vehicle Node Embedded Block Diagram

```mermaid
flowchart LR
    subgraph Sensors["Perception Layer"]
        US["HC-SR04 Transducer"] -->|"Pulse Echo"| SM["Sensor Manager"]
        BRK["Emergency Brake"] -->|"Active Low"| SM
    end

    subgraph CoreEngine["Edge Computing Core"]
        SM --> Risk["Risk & TTC Engine"]
        SM --> Prio["Priority Engine"]
        Prot["V2V Protocol Driver"] -->|"Incoming Packet"| Gate{"CRC16 & Version Check"}
        Gate -->|"Valid"| Watch["Fallback Watchdog"]
        Gate -->|"Valid"| Haz["Hazard Memory Latch"]
        Haz --> Risk
        Watch --> Risk
        Risk --> Prio
    end

    subgraph HMI["Cockpit HMI & Actuators"]
        Risk --> OLED["SSD1306 0.96 OLED"]
        Risk --> LED["Red/Green LEDs"]
        Risk --> Buzz["Piezo Buzzer"]
    end

    subgraph Comm["RF Transceiver"]
        Prio -->|"Emergency Burst (<5ms)"| ESP["ESP-NOW 2.4 GHz"]
        Prio -->|"Adaptive Beacon"| ESP
    end
```

---

## 3. V2V Emergency Preemption Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant D1 as Dumper 1 (Driver)
    participant N1 as Node 1 (ESP32)
    participant Air as 2.4 GHz Air Interface
    participant N2 as Node 2 (ESP32)
    participant D2 as Dumper 2 (Driver)

    Note over N1,N2: Routine 10 Hz Beaconing (SAFE State)
    N1->>Air: Beacon Packet (Priority: 0x03, No Hazard)
    Air->>N2: Beacon Received (CRC16 OK)
    N2->>D2: OLED: SAFE / DIST: 35m

    Note over D1: Emergency! Driver slams brake pedal
    D1->>N1: Brake Button Depressed (GPIO 19 LOW)
    rect rgb(255, 220, 220)
    Note over N1: Safety-Path Preemption: Bypass ML Queues!
    N1->>Air: EMERGENCY Frame (Priority: 0x00, Flag: BRAKE_ACTIVE)
    Air->>N2: Frame Received (<5 ms)
    end
    N2->>N2: CRC16 OK, Monotonic Seq OK
    N2->>N2: Latch Hazard State (1500 ms Hold)
    N2->>D2: Continuous Loud Buzzer Tone
    N2->>D2: Solid RED Danger LED ON
    N2->>D2: OLED: !! CRITICAL: EMERGENCY BRAKE !!
    Note over D2: Driver 2 hits retarder 50m before optical sight
```

---

## 4. Edge Collision Risk Decision Flowchart

```mermaid
flowchart TD
    Start["Sample Distance (d) and Velocity (v_rel)"] --> CheckPeerBrake{"Peer Brake Active?"}
    CheckPeerBrake -- Yes --> Critical["RISK_CRITICAL: Solid RED LED, Continuous Buzzer"]
    CheckPeerBrake -- No --> CalcTTC["Compute TTC = d / v_rel"]
    CalcTTC --> CheckCrit{"d <= 4m OR TTC <= 1.5s?"}
    CheckCrit -- Yes --> Critical
    CheckCrit -- No --> CheckWarn{"d <= 8m OR TTC <= 3.0s?"}
    CheckWarn -- Yes --> Warning["RISK_WARNING: Flashing RED LED (4Hz), Pulsing Buzzer"]
    CheckWarn -- No --> CheckCaut{"d <= 15m OR TTC <= 5.0s?"}
    CheckCaut -- Yes --> Caution["RISK_CAUTION: Green LED, 1Hz Chirp"]
    CheckCaut -- No --> Safe["RISK_SAFE: Green LED Steady, Buzzer Silent"]
```

---

## 5. Fail-Safe Fallback State Machine

```mermaid
stateDiagram-v2
    [*] --> BOOT: Power Applied
    BOOT --> FALLBACK_AUTONOMOUS: Init Peripheral Hardware
    
    state FALLBACK_AUTONOMOUS {
        [*] --> DegradedNotice
        DegradedNotice: OLED 'MODE: AUTONOMOUS'
        DegradedNotice: Sensor Local Pings Only
        DegradedNotice: Slow Amber Chime
    }

    FALLBACK_AUTONOMOUS --> V2V_COOPERATIVE_ACTIVE: Valid V2V Packet (CRC OK)
    
    state V2V_COOPERATIVE_ACTIVE {
        [*] --> NormalOperation
        NormalOperation: OLED 'V2V: OK (RX: count)'
        NormalOperation: Virtual Line-of-Sight (50m+)
        NormalOperation: ML Dynamic Rate Adaptation
    }

    V2V_COOPERATIVE_ACTIVE --> FALLBACK_AUTONOMOUS: Peer Silence > 2500 ms (Timeout)
```

---

## 6. Technology Evolution & Research Lineage

```mermaid
flowchart LR
    P1["Phase 1: Historical Baseline<br>- CC2500 2.4 GHz Transceiver<br>- Point-to-point raw packets<br>- Status: ARCHIVED"] 
    --> P2["Phase 2: DAAS-V2V ML Engine<br>- 85,248 synthetic records<br>- XGBoost density & congestion<br>- 99.72% Acc / 0.9301 AUC<br>- Status: IMPLEMENTED (HOST/SIM)"]
    --> P3["Phase 3: SIH26007 Prototype<br>- Dual ESP32 physical nodes<br>- Wire Protocol v2.0 (CRC16)<br>- Safety-path preemption (<5ms)<br>- Cockpit OLED/Buzzer/LED<br>- Fallback watchdog (2.5s)<br>- Status: FUNCTIONAL ON BENCH"]
    --> P4["Phase 4: Industrial Scale-Up<br>- 77 GHz mmWave Radar (TI AWR1843)<br>- Uncooled LWIR Thermal Vision<br>- 3GPP C-V2X (5.9 GHz PC5)<br>- DGMS Surface Mining Certification<br>- Status: ROADMAP TARGET"]
```
