# Message Freshness & Timing Budget Specification

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet System  
**Document Type:** Protocol Freshness & Temporal Integrity Analysis  

---

## 1. The Temporal Danger in Heavy Mine Fleets

In open-cast iron ore mining, a 150-ton loaded haul dumper traveling at 30 km/h covers approximately **8.33 meters every second**. 

If a collision avoidance system processes stale or delayed telemetry:
- A delay of **200 ms** translates to **1.67 meters** of unguided vehicle motion.
- A delay of **500 ms** translates to **4.17 meters** of unguided vehicle motion.
- A delay of **1000 ms** translates to **8.33 meters**, exceeding the critical stopping margin in dense fog.

Therefore, any telemetry message older than a strict freshness threshold must be flagged as stale and discarded from kinematic collision projections.

---

## 2. Freshness Specification & Verification

### Timestamp Invariant
Every transmitted wire packet includes a 32-bit millisecond monotonic sender timestamp:
`packet->timestamp_ms = millis();`

Upon frame reception at local time $T_{now}$:
$$\text{Message Age } \Delta t = T_{now} - \text{packet.timestamp\_ms}$$

### Evaluation Rules:
1. **Fresh Frame ($\Delta t \le 500\text{ ms}$):** The packet is verified and forwarded to the `RiskEngine` for active TTC calculation.
2. **Stale Frame ($\Delta t > 500\text{ ms}$):** The packet is flagged with `V2V_ERR_STALE_TIMESTAMP`. Kinematic positions are ignored, and a warning log is recorded.
3. **Future Frame ($\text{packet.timestamp\_ms} > T_{now} + 1000\text{ ms}$):** Indicates clock skew or uncoordinated boot time; accepted provisionally for relative delta checks but flagged for time synchronization re-audit.

---

## 3. End-to-End Latency Budget

```
+------------------------------------+----------------+
| Component / Processing Stage       | Latency Budget |
+------------------------------------+----------------+
| Sensor Read & Median Filter        | 2.0 ms         |
| Priority Arbitration & Struct Pack | 0.2 ms         |
| CRC16-CCITT Hardware Sign          | 0.1 ms         |
| ESP-NOW MAC Transmit (OTA Air)     | 1.5 ms         |
| ESP-NOW RX Interrupt & Copy        | 0.8 ms         |
| CRC16 Verification & Bounds Check  | 0.2 ms         |
| TTC Computation & Risk Evaluation  | 0.1 ms         |
| OLED & Buzzer HMI Driver Update    | 2.5 ms         |
+------------------------------------+----------------+
| TOTAL END-TO-END LATENCY           | < 7.4 ms       |
+------------------------------------+----------------+
```
This latency budget easily satisfies the 10 ms safety requirement for automotive emergency preemption.
