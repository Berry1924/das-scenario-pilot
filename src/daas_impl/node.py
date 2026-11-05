"""Vehicle node — VS1/VS2: adaptive beaconing, emergency isolation, ACK-RTT client.

Mirrors the firmware behaviour of vehicle-node/src/priority_engine (adaptive
beacon interval 50-500 ms) and common/safety/safety_isolation.h (emergency
frames bypass the rate limiter and are never throttled).

RTT semantics (contract section 2): strict sender-side ACK RTT. The sender
records TX(seq) start time; when an ACK(seq) arrives it computes
rtt = now - tx_start. No one-way delay is derived from independent clocks.
"""

from dataclasses import dataclass, field

from . import packet as P
from .packet import V2VPacket
from .ttc import RiskThresholds, assess_risk

FULL_RATE_INTERVAL_MS = 50.0     # 20 Hz maximum rate (emergency / active hazard)


@dataclass
class NodeConfig:
    node_id: int
    vehicle_type: int = P.VEHICLE_TYPE_HAUL_DUMPER_100T
    nominal_interval_ms: float = 100.0    # 10 Hz
    min_interval_ms: float = 50.0         # 20 Hz ceiling
    max_interval_ms: float = 500.0        # 2 Hz floor
    policy: str = "fixed"                 # "fixed" | "adaptive"
    emergency_isolation: bool = True      # C: emergency bypasses rate limiter
    neighbors_ref: float = 20.0           # density reference for adaptation
    thresholds: RiskThresholds = field(default_factory=RiskThresholds)


@dataclass
class NodeState:
    distance_m: float = 50.0
    speed_mps: float = 0.0
    accel_mps2: float = 0.0
    brake_active: bool = False


class VehicleNode:
    def __init__(self, cfg: NodeConfig):
        self.cfg = cfg
        self.state = NodeState()
        self.tx_seq = 0
        self.last_tx_ms = -1e12
        self.current_interval_ms = cfg.nominal_interval_ms
        self.pending_acks: dict[int, float] = {}   # seq -> tx_start_ms
        self.rtt_samples_ms: list[float] = []
        self.rtt_timeout_ms = 2000.0
        self.tx_count = 0
        self.rx_count = 0
        self.ack_count = 0

    # ---------------- kinematics ----------------

    def set_state(self, distance_m: float, speed_mps: float,
                  accel_mps2: float = 0.0, brake_active: bool = False) -> None:
        self.state = NodeState(distance_m, speed_mps, accel_mps2, brake_active)

    def is_emergency(self) -> bool:
        a = assess_risk(self.state.distance_m, self.state.speed_mps,
                        self.cfg.thresholds, brake_active=self.state.brake_active)
        return a.imminent_collision

    # ---------------- rate adaptation ----------------

    def desired_interval_ms(self, neighbor_count: float) -> float:
        if self.cfg.policy == "fixed":
            return self.cfg.nominal_interval_ms
        density_factor = neighbor_count / max(self.cfg.neighbors_ref, 1.0)
        interval = self.cfg.nominal_interval_ms * (1.0 + density_factor)
        return min(max(interval, self.cfg.min_interval_ms), self.cfg.max_interval_ms)

    # ---------------- transmission ----------------

    def maybe_transmit(self, now_ms: float, neighbor_count: float) -> V2VPacket | None:
        """Rate-limited beacon TX; emergency frames bypass the adaptive limiter.

        Isolation semantics: an emergency frame is transmitted as soon as the
        max-rate (20 Hz) slot is due — it never waits for the slower adaptive
        beacon slot. Without isolation (A/B), emergencies are queued behind
        the adaptive rate limiter (the documented failure mode).
        """
        emergency = self.is_emergency()
        if emergency and self.cfg.emergency_isolation:
            self.current_interval_ms = FULL_RATE_INTERVAL_MS
            if now_ms - self.last_tx_ms >= FULL_RATE_INTERVAL_MS:
                return self._build_and_mark(now_ms, emergency=True)
            return None

        self.current_interval_ms = self.desired_interval_ms(neighbor_count)
        if now_ms - self.last_tx_ms < self.current_interval_ms:
            return None
        return self._build_and_mark(now_ms, emergency=emergency)

    def _build_and_mark(self, now_ms: float, emergency: bool) -> V2VPacket:
        self.tx_seq += 1
        pkt = V2VPacket(
            sender_id=self.cfg.node_id,
            seq_num=self.tx_seq,
            timestamp_ms=int(now_ms),
            priority=P.PRIORITY_EMERGENCY if emergency else P.PRIORITY_BEACON,
            vehicle_type=self.cfg.vehicle_type,
            distance_m=self.state.distance_m,
            speed_mps=self.state.speed_mps,
            accel_mps2=self.state.accel_mps2,
        )
        pkt.sign()
        self.last_tx_ms = now_ms
        self.pending_acks[pkt.seq_num] = now_ms
        self.tx_count += 1
        return pkt

    # ---------------- receive / ACK ----------------

    def on_receive(self, pkt: V2VPacket, now_ms: float) -> bool:
        self.rx_count += 1
        return True

    def make_ack(self, pkt: V2VPacket, now_ms: float) -> V2VPacket:
        ack = V2VPacket(
            sender_id=self.cfg.node_id,
            seq_num=pkt.seq_num,
            timestamp_ms=int(now_ms),
            priority=P.PRIORITY_CONTROL,
            vehicle_type=self.cfg.vehicle_type,
        )
        ack.sign()
        return ack

    def on_ack(self, seq: int, now_ms: float) -> float | None:
        """Sender-side ACK RTT: pair ACK(seq) with pending TX(seq)."""
        tx_start = self.pending_acks.pop(seq, None)
        if tx_start is None:
            return None
        self.ack_count += 1
        rtt = now_ms - tx_start
        self.rtt_samples_ms.append(rtt)
        return rtt

    def expire_pending_acks(self, now_ms: float) -> None:
        stale = [s for s, t in self.pending_acks.items() if now_ms - t > self.rtt_timeout_ms]
        for s in stale:
            del self.pending_acks[s]
