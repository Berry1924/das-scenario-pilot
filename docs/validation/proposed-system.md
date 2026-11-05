# Proposed System: Risk-Aware Cooperative V2V with Safety-Path Isolation

**Configuration:** DAAS-V2V / SIH26007 Complete Integrated System  
**Evaluation Role:** Proposed Architectural Solution  

---

## 1. Description of Proposed System

The proposed system synergistically unites low-latency edge computing with supervisory machine learning intelligence:
1. **Safety-Path Preemption:** Life-critical emergency packets (`PRIORITY_EMERGENCY`) bypass all software rate limits and ML queues, transmitting immediately in $<5\text{ ms}$.
2. **Supervisory ML Rate Control:** For routine beacons, the DAAS-V2V ML model monitors channel congestion and dynamically adjusts transmission frequency (2 Hz in dense queues to 20 Hz in sparse open roads).
3. **Hazard Memory Latching:** Latches active warnings for 1500 ms to eliminate strobe flicker during intermittent RF loss.
4. **Deterministic Fallback:** Automatically switches to autonomous sensing within 2.5 seconds upon peer silence.

---

## 2. Experimental Verification Across Failure Scenarios

```
+-----------------------------------------------------------------------------------+
|                        SCENARIO VERIFICATION COMPARISON                           |
+--------------------------+------------------+------------------+------------------+
| Operational Scenario     | Baseline A       | Baseline B       | Proposed System  |
+--------------------------+------------------+------------------+------------------+
| Zero Fog Optical Vis     | CRASH (Blind)    | Safe if PDR OK   | SAFE (V2V virtual|
| (<5m line of sight)      |                  |                  | vision at 50m+)  |
+--------------------------+------------------+------------------+------------------+
| High Density Fleet       | N/A              | Channel overload;| SAFE (ML drops   |
| (Crusher Hopper Queue)   |                  | PDR drops to 52% | beacons to 2 Hz; |
|                          |                  |                  | PDR stays >89%)  |
+--------------------------+------------------+------------------+------------------+
| Emergency Hard Brake     | Sensor warning   | Latency 45-180ms | Instant warning  |
| by Preceding Dumper      | only at <4m      | (queued behind)  | (<5ms delivery)  |
+--------------------------+------------------+------------------+------------------+
| Deep Pit RF Shadowing    | No change        | Hangs or keeps   | Chime & fallback |
| (Peer radio blocked)     |                  | showing stale ok | to local sensors |
+--------------------------+------------------+------------------+------------------+
```
