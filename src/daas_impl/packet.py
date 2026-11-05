"""Byte-compatible Python mirror of the DAAS-V2V Wire Protocol v2.0 packet.

Mirrors firmware/common/protocol/v2v_packet.h and
firmware/common/validation/packet_validator.h (32-byte packed struct,
CRC16-CCITT poly 0x1021 init 0xFFFF, no final XOR, MSB-first).
Contract: docs/implementation/CURRENT_INTERFACE_CONTRACT.md section 1.
"""

import struct
from dataclasses import dataclass, field

V2V_MAGIC_BYTE = 0xD4
V2V_PROTOCOL_VERSION = 0x02
V2V_BROADCAST_ID = 0xFF
V2V_PACKET_SIZE = 32
V2V_CRC_OFFSET = 30

PRIORITY_EMERGENCY = 0x00
PRIORITY_CONTROL = 0x01
PRIORITY_WARNING = 0x02
PRIORITY_BEACON = 0x03
PRIORITY_NAMES = {0x00: "EMERGENCY", 0x01: "CONTROL", 0x02: "WARNING", 0x03: "BEACON"}

VEHICLE_TYPE_UNKNOWN = 0x00
VEHICLE_TYPE_HAUL_DUMPER_85T = 0x01
VEHICLE_TYPE_HAUL_DUMPER_100T = 0x02
VEHICLE_TYPE_HAUL_DUMPER_240T = 0x03
VEHICLE_TYPE_SHOVEL_EXCAVATOR = 0x04
VEHICLE_TYPE_WATER_BOWSER = 0x05
VEHICLE_TYPE_MOTOR_GRADER = 0x06
VEHICLE_TYPE_LIGHT_VEHICLE = 0x07
VEHICLE_TYPE_ROADSIDE_UNIT = 0x08

HAZARD_FLAG_NONE = 0x0000
HAZARD_FLAG_BRAKE_ACTIVE = 1 << 0
HAZARD_FLAG_IMMINENT_COLLISION = 1 << 1
HAZARD_FLAG_STALLED_VEHICLE = 1 << 2
HAZARD_FLAG_LOW_VISIBILITY_FOG = 1 << 3
HAZARD_FLAG_BERM_PROXIMITY = 1 << 4
HAZARD_FLAG_SENSOR_FAULT = 1 << 5

RISK_LEVEL_SAFE = 0
RISK_LEVEL_CAUTION = 1
RISK_LEVEL_WARNING = 2
RISK_LEVEL_CRITICAL = 3
RISK_LEVEL_NAMES = {0: "SAFE", 1: "CAUTION", 2: "WARNING", 3: "CRITICAL"}

# Validation result codes (mirrors v2v_validation_result_t)
V2V_VALID_OK = 0x00
V2V_ERR_NULL_POINTER = 0x01
V2V_ERR_BAD_MAGIC = 0x02
V2V_ERR_UNSUPPORTED_VERSION = 0x03
V2V_ERR_CRC_MISMATCH = 0x04
V2V_ERR_STALE_TIMESTAMP = 0x05
V2V_ERR_OUT_OF_BOUNDS = 0x06
V2V_ERR_DUPLICATE_SEQUENCE = 0x07
VALIDATION_NAMES = {
    0x00: "OK",
    0x01: "NULL_POINTER",
    0x02: "BAD_MAGIC",
    0x03: "UNSUPPORTED_VERSION",
    0x04: "CRC_MISMATCH",
    0x05: "STALE_TIMESTAMP",
    0x06: "OUT_OF_BOUNDS",
    0x07: "DUPLICATE_SEQUENCE",
}

V2V_MAX_MESSAGE_AGE_MS = 500

_STRUCT = struct.Struct("<BBBBBBHIIfffbBH")  # little-endian, 32 bytes total


def compute_crc16(data: bytes) -> int:
    """CRC16-CCITT: poly 0x1021, init 0xFFFF, no final XOR, MSB-first.

    Bit-identical to v2v_compute_crc16() in packet_validator.h.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


@dataclass
class V2VPacket:
    sender_id: int
    seq_num: int
    timestamp_ms: int
    priority: int = PRIORITY_BEACON
    target_id: int = V2V_BROADCAST_ID
    vehicle_type: int = VEHICLE_TYPE_HAUL_DUMPER_100T
    hazard_flags: int = HAZARD_FLAG_NONE
    distance_m: float = 0.0
    speed_mps: float = 0.0
    accel_mps2: float = 0.0
    rssi_dbm: int = -127
    reserved: int = 0
    crc16: int = 0

    def to_bytes(self) -> bytes:
        payload = _STRUCT.pack(
            V2V_MAGIC_BYTE,
            V2V_PROTOCOL_VERSION,
            self.priority & 0xFF,
            self.sender_id & 0xFF,
            self.target_id & 0xFF,
            self.vehicle_type & 0xFF,
            self.hazard_flags & 0xFFFF,
            self.seq_num & 0xFFFFFFFF,
            self.timestamp_ms & 0xFFFFFFFF,
            self.distance_m,
            self.speed_mps,
            self.accel_mps2,
            max(-128, min(127, int(self.rssi_dbm))),
            self.reserved & 0xFF,
            self.crc16 & 0xFFFF,
        )
        if len(payload) != V2V_PACKET_SIZE:
            raise ValueError(f"packed size {len(payload)} != {V2V_PACKET_SIZE}")
        return payload

    def sign(self) -> "V2VPacket":
        raw = self.to_bytes()
        self.crc16 = compute_crc16(raw[:V2V_CRC_OFFSET])
        return self

    @classmethod
    def from_bytes(cls, raw: bytes) -> "V2VPacket":
        if len(raw) != V2V_PACKET_SIZE:
            raise ValueError(f"frame size {len(raw)} != {V2V_PACKET_SIZE}")
        (magic, version, priority, sender_id, target_id, vehicle_type,
         hazard_flags, seq_num, timestamp_ms, distance_m, speed_mps,
         accel_mps2, rssi_dbm, reserved, crc16) = _STRUCT.unpack(raw)
        if magic != V2V_MAGIC_BYTE:
            raise ValueError(f"bad magic 0x{magic:02X}")
        pkt = cls(
            sender_id=sender_id,
            seq_num=seq_num,
            timestamp_ms=timestamp_ms,
            priority=priority,
            target_id=target_id,
            vehicle_type=vehicle_type,
            hazard_flags=hazard_flags,
            distance_m=distance_m,
            speed_mps=speed_mps,
            accel_mps2=accel_mps2,
            rssi_dbm=rssi_dbm,
            reserved=reserved,
            crc16=crc16,
        )
        pkt._raw_version = version
        return pkt

    def is_safety_critical(self) -> bool:
        return (
            self.priority == PRIORITY_EMERGENCY
            or (self.hazard_flags & (HAZARD_FLAG_BRAKE_ACTIVE | HAZARD_FLAG_IMMINENT_COLLISION)) != 0
        )


def validate_packet(pkt: V2VPacket, current_time_ms: int | None = None,
                    crc_enabled: bool = True) -> int:
    """Structural + integrity validation. Mirrors v2v_validate_packet().

    current_time_ms=None skips the freshness check (no receiver clock context).
    Returns a V2V_VALID_OK / V2V_ERR_* code.
    """
    if pkt is None:
        return V2V_ERR_NULL_POINTER
    if crc_enabled:
        raw = pkt.to_bytes()
        if compute_crc16(raw[:V2V_CRC_OFFSET]) != pkt.crc16:
            return V2V_ERR_CRC_MISMATCH
    if current_time_ms is not None and current_time_ms >= pkt.timestamp_ms:
        age_ms = current_time_ms - pkt.timestamp_ms
        if age_ms > V2V_MAX_MESSAGE_AGE_MS:
            return V2V_ERR_STALE_TIMESTAMP
    if pkt.distance_m < 0.0 or pkt.distance_m > 5000.0:
        return V2V_ERR_OUT_OF_BOUNDS
    if pkt.speed_mps < -30.0 or pkt.speed_mps > 70.0:
        return V2V_ERR_OUT_OF_BOUNDS
    if pkt.accel_mps2 < -25.0 or pkt.accel_mps2 > 20.0:
        return V2V_ERR_OUT_OF_BOUNDS
    return V2V_VALID_OK


def validate_sequence(new_seq: int, last_seq: int) -> tuple[bool, int]:
    """Monotonic sequence check. Returns (is_valid, dropped_count).

    Mirrors v2v_validate_sequence(); is_valid=False means duplicate/replay.
    """
    if last_seq == 0 and new_seq > 0:
        return True, 0
    if new_seq > last_seq:
        return True, (new_seq - last_seq) - 1
    return False, 0
