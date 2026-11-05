"""Trust gate — VS3.

Application-layer verification chain (NO PKI; sequence/freshness/plausibility
only, mirroring firmware/common/validation/packet_validator.h):

  1. CRC16-CCITT integrity
  2. Monotonic sequence validation + duplicate/replay detection (per sender)
  3. Freshness (age <= tau_max, receiver-referenced)
  4. Kinematic plausibility (speed/accel/distance bounds)
  5. Local/remote consistency indicator (down-weight, never silent suppression
     of emergency events — emergency frames flagged as inconsistent are still
     accepted but marked downweighted)

Fault-injection hooks exist for: stale, duplicate, invalid sequence,
impossible speed, impossible distance.
"""

from dataclasses import dataclass, field

from . import packet as P
from .packet import V2VPacket

DEFAULT_TAU_MAX_MS = 500
SPEED_MIN_MPS = -30.0
SPEED_MAX_MPS = 70.0
ACCEL_MIN_MPS2 = -25.0
ACCEL_MAX_MPS2 = 20.0
DIST_MAX_M = 5000.0


@dataclass
class TrustGateConfig:
    tau_max_ms: int = DEFAULT_TAU_MAX_MS
    crc_enabled: bool = True
    sequence_enabled: bool = True
    freshness_enabled: bool = True
    plausibility_enabled: bool = True
    consistency_enabled: bool = True


@dataclass
class GateDecision:
    accepted: bool
    rejected: bool
    downweighted: bool
    code: int                     # V2V_VALID_OK / V2V_ERR_* / DUPLICATE_SEQUENCE
    age_ms: float
    inconsistency_flag: bool


@dataclass
class _PeerState:
    last_seq: int = 0
    last_distance_m: float | None = None
    last_timestamp_ms: int | None = None


class TrustGate:
    """Per-receiver trust gate with per-sender sequence trackers."""

    def __init__(self, cfg: TrustGateConfig | None = None):
        self.cfg = cfg or TrustGateConfig()
        self.peers: dict[int, _PeerState] = {}
        self.counts = {
            "received": 0, "accepted": 0, "rejected": 0, "downweighted": 0,
            "rej_crc": 0, "rej_duplicate": 0, "rej_sequence": 0,
            "rej_stale": 0, "rej_bounds": 0, "rej_inconsistent": 0,
        }

    def _peer(self, sender_id: int) -> _PeerState:
        if sender_id not in self.peers:
            self.peers[sender_id] = _PeerState()
        return self.peers[sender_id]

    def ingest(self, pkt: V2VPacket, now_ms: float,
               local_distance_m: float | None = None) -> GateDecision:
        """Ingest one frame at receiver time now_ms (simulated single clock)."""
        self.counts["received"] += 1
        peer = self._peer(pkt.sender_id)

        age_ms = max(0.0, now_ms - pkt.timestamp_ms)
        inconsistent = False

        if self.cfg.crc_enabled:
            raw = pkt.to_bytes()
            if P.compute_crc16(raw[:P.V2V_CRC_OFFSET]) != pkt.crc16:
                self.counts["rejected"] += 1
                self.counts["rej_crc"] += 1
                return GateDecision(False, True, False, P.V2V_ERR_CRC_MISMATCH, age_ms, False)

        if self.cfg.sequence_enabled:
            ok, _dropped = P.validate_sequence(pkt.seq_num, peer.last_seq)
            if not ok:
                self.counts["rejected"] += 1
                self.counts["rej_duplicate"] += 1
                return GateDecision(False, True, False, P.V2V_ERR_DUPLICATE_SEQUENCE, age_ms, False)

        if self.cfg.freshness_enabled and age_ms > self.cfg.tau_max_ms:
            self.counts["rejected"] += 1
            self.counts["rej_stale"] += 1
            return GateDecision(False, True, False, P.V2V_ERR_STALE_TIMESTAMP, age_ms, False)

        if self.cfg.plausibility_enabled:
            if pkt.distance_m < 0.0 or pkt.distance_m > DIST_MAX_M:
                self.counts["rejected"] += 1
                self.counts["rej_bounds"] += 1
                return GateDecision(False, True, False, P.V2V_ERR_OUT_OF_BOUNDS, age_ms, False)
            if not (SPEED_MIN_MPS <= pkt.speed_mps <= SPEED_MAX_MPS):
                self.counts["rejected"] += 1
                self.counts["rej_bounds"] += 1
                return GateDecision(False, True, False, P.V2V_ERR_OUT_OF_BOUNDS, age_ms, False)
            if not (ACCEL_MIN_MPS2 <= pkt.accel_mps2 <= ACCEL_MAX_MPS2):
                self.counts["rejected"] += 1
                self.counts["rej_bounds"] += 1
                return GateDecision(False, True, False, P.V2V_ERR_OUT_OF_BOUNDS, age_ms, False)

        if self.cfg.consistency_enabled and local_distance_m is not None and peer.last_distance_m is not None:
            peer_claimed_gap = abs(peer.last_distance_m - pkt.distance_m)
            implied_speed = peer_claimed_gap / max(age_ms / 1000.0, 1e-6) if age_ms > 0 else 0.0
            if implied_speed > SPEED_MAX_MPS:
                inconsistent = True

        peer.last_seq = pkt.seq_num
        peer.last_distance_m = pkt.distance_m
        peer.last_timestamp_ms = pkt.timestamp_ms

        if inconsistent:
            self.counts["downweighted"] += 1
            self.counts["accepted"] += 1
            return GateDecision(True, False, True, P.V2V_VALID_OK, age_ms, True)

        self.counts["accepted"] += 1
        return GateDecision(True, False, False, P.V2V_VALID_OK, age_ms, False)
