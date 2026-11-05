# Wire Protocol Specification (v2.0)

**Project:** DAAS-V2V / SIH26007 Cooperative Mine Fleet System  
**Specification Version:** 2.0.0  
**Transport Layers:** ESP-NOW 2.4 GHz (Physical Bench Prototype), 3GPP C-V2X PC5 (Roadmap)  
**Byte Alignment:** 1-Byte Packed (`#pragma pack(push, 1)`)  
**Byte Endianness:** Little-Endian (ESP32 / ARM native)  

---

## 1. Frame Structure & Byte Offsets

The V2V wire packet is an unfragmented 32-byte frame optimized for sub-millisecond serialization and low-overhead RF transmission.

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|  Magic (0xD4) |  Version(0x02)| Priority(0-3) | Sender ID(1-254)
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| Target ID(0xFF| VehType (1-8) |          Hazard Flags         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Sequence Number                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Timestamp Monotonic (ms)                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         Distance (m)                          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       Speed (meters/sec)                      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                  Longitudinal Accel (m/s^2)                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|  RSSI (dBm)   |  Reserved(0x00) |         CRC16-CCITT         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

---

## 2. Field-by-Field Definition

| Offset | Field Name | Data Type | Permitted Values | Functional Purpose |
| :---: | :--- | :--- | :--- | :--- |
| `0x00` | `magic` | `uint8_t` | `0xD4` | Protocol synchronization header. Frames lacking `0xD4` are discarded immediately. |
| `0x01` | `protocol_version` | `uint8_t` | `0x02` | Schema revision tracker. Mismatched versions are logged and dropped. |
| `0x02` | `priority` | `uint8_t` | `0x00` – `0x03` | Message priority level (`0x00` = Emergency, `0x03` = Routine Beacon). |
| `0x03` | `sender_id` | `uint8_t` | `1` – `254` | Unique network vehicle identifier. |
| `0x04` | `target_id` | `uint8_t` | `1` – `254`, `0xFF` | Recipient ID or `0xFF` for broadcast to all listening nodes. |
| `0x05` | `vehicle_type` | `uint8_t` | `0x00` – `0x08` | Machine classification: Haul Dumper, Excavator, Water Bowser, etc. |
| `0x06` | `hazard_flags` | `uint16_t` | Bitmask | Active safety alerts (Brake Active, Collision Risk, Stalled Vehicle). |
| `0x08` | `seq_num` | `uint32_t` | Monotonic | Sender packet sequence counter for drop detection and replay protection. |
| `0x0C` | `timestamp_ms` | `uint32_t` | Monotonic clock | Local uptime timestamp in milliseconds for message freshness audit. |
| `0x10` | `distance_m` | `float` (IEEE 754)| $0.0 \le d \le 5000.0$ | Forward distance to preceding vehicle or obstacle in meters. |
| `0x14` | `speed_mps` | `float` (IEEE 754)| $-30.0 \le v \le 70.0$ | Vehicle forward speed in meters per second ($1\text{ m/s} = 3.6\text{ km/h}$). |
| `0x18` | `accel_mps2` | `float` (IEEE 754)| $-25.0 \le a \le 20.0$ | Longitudinal acceleration in $\text{m/s}^2$ (negative denotes braking). |
| `0x1C` | `rssi_dbm` | `int8_t` | $-128 \le \text{rssi} \le 0$ | RF signal strength indicator in dBm recorded at receiver. |
| `0x1D` | `reserved` | `uint8_t` | `0x00` | Padding byte for 32-bit boundary alignment. |
| `0x1E` | `crc16` | `uint16_t` | Checksum | CRC16-CCITT polynomial `0x1021` computed across bytes `0x00`..`0x1D`. |

---

## 3. Hazard Flags Bitmask Specification

Hazard flags represent discrete safety states:

| Bit Position | Hex Mask | Flag Constant | Meaning in Open-Cast Mine Operations |
| :---: | :---: | :--- | :--- |
| Bit 0 | `0x0001` | `HAZARD_FLAG_BRAKE_ACTIVE` | Operator has depressed emergency foot brake or retarder lever. |
| Bit 1 | `0x0002` | `HAZARD_FLAG_IMMINENT_COLLISION` | Local edge risk engine calculated TTC below critical threshold ($<1.5\text{s}$). |
| Bit 2 | `0x0004` | `HAZARD_FLAG_STALLED_VEHICLE` | Vehicle has broken down or suffered engine failure in haul road. |
| Bit 3 | `0x0008` | `HAZARD_FLAG_LOW_VISIBILITY_FOG` | Dense fog / airborne hematite dust cloud causing zero cabin visibility. |
| Bit 4 | `0x0010` | `HAZARD_FLAG_BERM_PROXIMITY` | Dumper dangerously close to bench drop-off edge or safety berm breach. |
| Bit 5 | `0x0020` | `HAZARD_FLAG_SENSOR_FAULT` | Local obstacle ranging sensor timeout, acoustic noise lockup, or failure. |

---

## 4. Cyclic Redundancy Check (CRC16) Algorithm

- **Polynomial:** $x^{16} + x^{12} + x^5 + 1$ (`0x1021`)
- **Initial Value:** `0xFFFF`
- **Output XOR:** `0x0000`
- **Calculation Window:** Bytes 0 to 29 inclusive (30 bytes total). Bytes 30 and 31 store the calculated CRC16.
- **Verification Rule:** If `v2v_compute_crc16(buf, 30) != packet->crc16`, the frame is discarded immediately.
