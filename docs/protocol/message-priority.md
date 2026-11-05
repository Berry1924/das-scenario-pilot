# Message Priority & Quality of Service (QoS) Architecture

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet System  
**Specification Reference:** Safety-Path Priority Dispatcher  

---

## 1. Priority Classes & Service Guarantees

The protocol defines four distinct priority classes designed to ensure that life-critical hazard broadcasts never compete with routine fleet position telemetry:

| Priority Value | Identifier | Triggering Event / Use Case | Transmission Policy | Target Latency Budget | Throttling Allowed? |
| :---: | :--- | :--- | :--- | :---: | :---: |
| `0x00` | `PRIORITY_EMERGENCY` | Driver slams emergency foot brake; local risk engine calculates TTC < 1.5s; imminent collision. | Immediate preemption burst (up to 20 Hz); zero queue delay. | **< 5 ms** | **STRICTLY FORBIDDEN** |
| `0x01` | `PRIORITY_CONTROL` | Safety berm proximity warning; disabled vehicle breakdown in haul road; dump-crest boundary alert. | Expedited transmission; minimum rate 10 Hz. | **< 20 ms** | No |
| `0x02` | `PRIORITY_WARNING` | Blind hairpin curve advisory; oncoming loaded dumper approaching single-lane haul cut. | Priority queue; nominal rate 5–10 Hz. | **< 50 ms** | Conditional |
| `0x03` | `PRIORITY_BEACON` | Routine kinematic position, speed, and heading telemetry for fleet tracking. | Rate-adapted dynamically by DAAS-V2V ML model (2 Hz to 20 Hz). | **< 250 ms** | **YES (ML Controlled)** |

---

## 2. Safety-Path Isolation Guarantees

### Invariant I-01: Zero ML Throttling for Safety Packets
The DAAS-V2V supervisory engine dynamically reduces transmission frequency during high vehicular density to prevent RF packet collision storms on the wireless medium. However, software verification tests (`firmware/tests/test_safety_isolation.cpp`) mathematically enforce that:
$$\forall p \in \text{Packets}, \quad \text{IsEmergency}(p) \implies \text{ThrottleAllowed}(p) = \text{False}$$

### Invariant I-02: Preemptive Queue Eviction
If a routine beacon is currently queued or scheduled, the arrival of an emergency brake event immediately overrides the transmission schedule, transmitting the `PRIORITY_EMERGENCY` frame immediately over the physical MAC layer.
