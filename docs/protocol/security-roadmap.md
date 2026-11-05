# Security Threat Model & Cryptographic Roadmap

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet System  
**Document Type:** Security Architecture & Cryptographic Roadmap  
**Current Security Status:** `PROTOTYPE / UNENCRYPTED BENCH BASELINE`  

---

## 1. Threat Model for Open-Cast Mine V2X Systems

In industrial surface mining, malicious actors, disgruntled personnel, or compromised IoT hardware present distinct attack vectors that could halt operations or induce catastrophic collisions:

```
+---------------------------------------------------------------------------------------------------+
|                                MINING V2X ATTACK TAXONOMY                                         |
+----------------------+-------------------------------------+--------------------------------------+
| Threat Category      | Attack Mechanism                    | Potential Safety & Operational Impact|
+----------------------+-------------------------------------+--------------------------------------+
| **Spoofing**         | Rogue node broadcasts fake          | Haul dumpers execute unnecessary     |
|                      | `HAZARD_FLAG_BRAKE_ACTIVE` frames.  | emergency stops; production halts.   |
+----------------------+-------------------------------------+--------------------------------------+
| **Replay Attacks**   | Attacker records genuine emergency  | Phantom hazard warnings trigger      |
|                      | frames and rebroadcasts them later. | warning fatigue in drivers.          |
+----------------------+-------------------------------------+--------------------------------------+
| **Sybil Attack**     | A single rogue transceiver creates  | Supervisory ML incorrectly assumes   |
|                      | dozens of virtual ghost vehicles.   | heavy congestion, throttling beacons.|
+----------------------+-------------------------------------+--------------------------------------+
| **RF Jamming / DoS** | Continuous high-power 2.4 GHz noise | Forces vehicle nodes into autonomous |
|                      | floods the wireless channel.        | fallback mode; eliminates virtual LOS|
+----------------------+-------------------------------------+--------------------------------------+
| **Tampering**        | Physical manipulation of sensors or | False distance/speed transmitted to  |
|                      | internal microcontroller memory.    | surrounding cooperative fleet.       |
+----------------------+-------------------------------------+--------------------------------------+
```

---

## 2. Current Prototype Security Boundaries & Truth

In the current physical bench prototype (Phase 3):
- **Transport:** Standard connectionless ESP-NOW over 2.4 GHz Wi-Fi MAC layer.
- **Integrity:** CRC16-CCITT checksum for corruption detection.
- **Sequence Protection:** Monotonic sequence numbers detect dropped and duplicate frames.
- **Cryptographic Status:** **No asymmetric digital signatures or AES encryption keys are currently active in bench firmware.** The prototype is configured in open laboratory mode for transparent RF sniffing and multi-node debugging.

> [!WARNING]
> Do not deploy the current bench firmware in a production or unmonitored mining environment without implementing the Phase 4 cryptographic enhancements detailed below.

---

## 3. Cryptographic Roadmap (Phase 4 Industrial Scale-Up)

To achieve compliance with automotive and industrial safety standards (ISO 21434, IEEE 1609.2):

### 3.1 Hardware Root of Trust
- Incorporate a dedicated cryptographic coprocessor (e.g., Microchip ATECC608B or Infineon OPTIGA Trust M) connected to the OBU host microcontroller via secure I2C.
- Store private vehicle signing keys in hardware tamper-resistant non-volatile memory.

### 3.2 IEEE 1609.2 Vehicle Public Key Infrastructure (VPKI)
- **Mine Dispatch Certificate Authority (CA):** Each mining vehicle is enrolled during shift-start dispatch inspection, receiving an ephemeral authorization certificate valid for 12 hours.
- **Asymmetric Frame Signing:** Every emergency frame is signed using **Ed25519** or **ECDSA (NIST P-256)** signatures. Receivers verify the digital signature against the authorized mine fleet registry before accepting emergency commands.

### 3.3 Symmetric Payload Encryption (AES-128-CCM)
- For proprietary dispatch telemetry, frames are encrypted using AES-128 in Counter with CBC-MAC (CCM) mode, providing both confidentiality and cryptographic authentication in hardware-accelerated time (<1 ms).

### 3.4 Jamming & DoS Resilience
- **Multi-Frequency Agility:** Automatic channel switching between 5.9 GHz C-V2X channels and backup 2.4 GHz industrial channels.
- **Fallback Watchdog:** Rapid transition to autonomous sensing (`FALLBACK_AUTONOMOUS`) within 2.5 seconds if jamming noise renders the wireless channel unusable.
