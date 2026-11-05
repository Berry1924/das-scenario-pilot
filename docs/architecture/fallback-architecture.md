# Fail-Safe Fallback & Degraded Mode Architecture

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet System  
**Document Type:** Fault Tolerance & System Safety Specification  

---

## 1. Principles of Fail-Safe Operation

A foundational principle of mine safety systems is: **A safety system must never fail silently.**

If wireless communications are severed by deep-pit rock wall occlusion, RF jamming, or hardware transceiver malfunction, the operator must be immediately alerted that the "electronic windshield" is offline and that the vehicle has transitioned into autonomous degraded mode.

---

## 2. Fallback State Machine

```
              +-----------------------------------------+
              |           STATE: SYSTEM BOOT            |
              |   - Initialize I2C, OLED, Sensors       |
              |   - Start ESP-NOW radio listener        |
              +-----------------------------------------+
                                   |
                                   v
+=======================================================================+
|                   STATE: FALLBACK_AUTONOMOUS (DEGRADED)               |
|   - V2V radio contact is absent or lost                               |
|   - Driver Alert: OLED shows "MODE: AUTONOMOUS / V2V OFFLINE"         |
|   - LED Indicator: Slow amber/green pulsing                           |
|   - Primary Guidance: Relies exclusively on local ultrasonic/radar    |
+=======================================================================+
                   |                                ^
                   | Valid V2V Packet Received      | Peer Silence > 2500 ms
                   | (CRC16 OK, Version OK)         | (Watchdog Timeout Expired)
                   v                                |
+=======================================================================+
|                   STATE: V2V_COOPERATIVE_ACTIVE (NORMAL)              |
|   - Bi-directional telemetry exchanged with peer fleet                |
|   - Cooperative early warnings enabled (50m+ virtual LOS)             |
|   - Driver Alert: OLED shows "V2V: OK (RX: count)"                    |
|   - Dynamic beaconing adapted by DAAS ML model                        |
+=======================================================================+
```

---

## 3. State Transition Rules & Invariants

### 3.1 Transition from Degraded to Active
- **Condition:** Arrival of a valid `v2v_packet_t` that satisfies:
  1. `packet.magic == 0xD4`
  2. `packet.protocol_version == 0x02`
  3. Calculated CRC16 matches `packet.crc16`
  4. Sequence number is monotonic ($S_{new} > S_{last}$)
- **Action:**
  - `FallbackManager::recordPeerHeartbeat(now)`
  - Clear fallback status flag.
  - Re-enable cooperative visual indicators.

### 3.2 Transition from Active to Degraded (Timeout Watchdog)
- **Watchdog Threshold:** `FALLBACK_TIMEOUT_MS = 2500 ms`
- **Condition:** No valid wire packet received from peer within 2500 milliseconds.
- **Action:**
  - Set `fallback_active = true`.
  - Issue low-frequency warning chime to operator.
  - Discard cached peer hazard flags.
  - Advise driver via OLED to maintain maximum headway distance and reduce speed.
