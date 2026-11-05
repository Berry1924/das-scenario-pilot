# Wire Packet Lifecycle & State Machine

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet Safety  
**Document Type:** Communication Protocol Engineering Specification  

---

## 1. End-to-End Packet Lifecycle

From initial physical event generation on the transmitter node to actionable safety warning rendering on the receiver node, each packet traverses eight deterministic stages:

```
TRANSMITTER NODE                                                RECEIVER NODE
================                                                =============

[ Physical Event / Sensor ]
  - Emergency Brake Switch Pressed
  - Ultrasonic Ping Echo
            |
            v
[ Priority Arbitration ]
  - Is it an emergency brake?
  - YES -> Priority = 0x00 (Emergency)
           Bypass ML Queues!
  - NO  -> Priority = 0x03 (Beacon)
           Paced by Adaptive Interval
            |
            v
[ Serialization & Signing ]
  - Populate 32-byte struct
  - Increment Sequence Number
  - Compute CRC16-CCITT (Bytes 0..29)
  - Store CRC in byte 30..31
            |
            v
[ Physical Layer Broadcast ]
  - ESP-NOW 2.4 GHz Action Frame (Bench)
  - C-V2X PC5 Sidelink Broadcast (Roadmap)
            |
            +~~~~~~~~~~~~~~~~~ AIR INTERFACE ~~~~~~~~~~~~~~~~~>
                                                              |
                                                              v
                                                    [ Physical Reception ]
                                                      - Hardware Wi-Fi MAC RX interrupt
                                                      - Copy payload into RAM buffer
                                                              |
                                                              v
                                                    [ Integrity & Sanity Gate ]
                                                      - Magic Byte == 0xD4?
                                                      - Protocol Version == 0x02?
                                                      - Calculated CRC16 == Packet CRC16?
                                                      - Kinematics within physical bounds?
                                                      (Drop frame if any check fails)
                                                              |
                                                              v
                                                    [ Freshness & Sequence Audit ]
                                                      - Message Age <= 500 ms?
                                                      - Sequence monotonic? (Detect loss)
                                                              |
                                                              v
                                                    [ State & Risk Integration ]
                                                      - Reset Fallback Watchdog (Peer alive)
                                                      - Latch Hazard Flags (Anti-flicker)
                                                      - Calculate TTC & Risk Level
                                                              |
                                                              v
                                                    [ Cockpit Action Delivery ]
                                                      - Render SSD1306 OLED Display
                                                      - Trigger Piezo Buzzer Warning Cadence
                                                      - Update Red/Green Warning LEDs
                                                      - Stream JSON Telemetry to Mine Gateway
```

---

## 2. Invariant Rules Across Lifecycle

1. **Safety Preemption:** An emergency frame in state `[Priority Arbitration]` immediately preempts any active background delays.
2. **Zero-Trust Memory Verification:** No received packet data enters the `RiskEngine` or `HazardStateManager` until it passes all checks in `[Integrity & Sanity Gate]`.
3. **Loss Accounting:** Dropped sequence numbers are counted and made available to the supervisory ML congestion model to monitor link degradation.
