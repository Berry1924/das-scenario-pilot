"""Discrete-event simulation world — VS1/VS2/C1 communication experiments.

SIMULATION ONLY (single simulated clock, deterministic under a fixed seed).
Integrates VehicleNode (adaptive beacon + emergency isolation), ChannelModel
(ESP-NOW-style lossy medium with ACK RTT), and TrustGate where enabled.

Simplifications (documented in every run's metadata):
- Per-frame delivery is decided once by the channel (shared medium); all
  in-range receivers receive a delivered frame. ACKs are subject to
  independent loss per receiver.
- Mobility is a simple deterministic-plus-noise haul-road model, not a
  traffic microsimulator.
- The adaptive policy is a deterministic density-aware surrogate, NOT the
  prior-work XGBoost model (which is PRIOR-WORK evidence and is not
  executed here).
"""

import math
from dataclasses import dataclass, field

from . import packet as P
from .channel import ChannelConfig, ChannelModel
from .node import NodeConfig, VehicleNode
from .trust_gate import TrustGate, TrustGateConfig


@dataclass
class WorldConfig:
    duration_s: float = 300.0
    dt_ms: float = 10.0
    n_nodes: int = 2
    road_length_m: float = 100.0
    comm_range_m: float = 100.0
    policy: str = "fixed"                 # "fixed" | "adaptive"
    emergency_isolation: bool = True
    emergency_lambda: float = 0.05        # Poisson arrivals per second (fleet-wide)
    emergency_duration_ms: float = 2000.0
    emergency_enabled: bool = True
    trust_gate_enabled: bool = False
    speed_mean_mps: float = 8.0
    speed_jitter_mps: float = 3.0


@dataclass
class EmergencyEvent:
    node_id: int
    start_ms: float
    end_ms: float


@dataclass
class WorldMetrics:
    frames_offered: int = 0
    frames_delivered: int = 0
    acks_generated: int = 0
    acks_received: int = 0
    rtt_samples_ms: list = field(default_factory=list)
    emergency_frames_offered: int = 0
    emergency_frames_delivered: int = 0
    emergency_rtt_samples_ms: list = field(default_factory=list)
    emergency_first_airtime_ms: list = field(default_factory=list)
    normal_frames_offered: int = 0
    normal_frames_delivered: int = 0
    normal_rtt_samples_ms: list = field(default_factory=list)
    bytes_tx: int = 0
    gate_accepted: int = 0
    gate_rejected: int = 0
    gate_downweighted: int = 0
    emergency_active_time_ms: float = 0.0
    emergency_one_way_ms: list = field(default_factory=list)
    events: list = field(default_factory=list)

    def pdr_pct(self) -> float:
        return 100.0 * self.frames_delivered / self.frames_offered if self.frames_offered else 0.0

    def emergency_pdr_pct(self) -> float:
        return (100.0 * self.emergency_frames_delivered / self.emergency_frames_offered
                if self.emergency_frames_offered else 0.0)


def percentile(values: list, p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


class SimulationWorld:
    """Time-stepped simulation of N vehicles on a haul road with V2V."""

    def __init__(self, wcfg: WorldConfig, ccfg: ChannelConfig, rng):
        self.wcfg = wcfg
        self.channel = ChannelModel(ccfg, rng)
        self.rng = rng
        self.nodes: list[VehicleNode] = []
        for i in range(1, wcfg.n_nodes + 1):
            ncfg = NodeConfig(
                node_id=i,
                policy=wcfg.policy,
                emergency_isolation=wcfg.emergency_isolation,
            )
            self.nodes.append(VehicleNode(ncfg))
        self.trust_gate = TrustGate(TrustGateConfig()) if wcfg.trust_gate_enabled else None
        self.positions: list[float] = []
        self.emergencies: list[EmergencyEvent] = []
        self._next_emergency_ms: float | None = None
        self._ack_queue: list[tuple[int, int, float, bool]] = []
        self._emergency_pending_start: dict[int, float] = {}

    # ---------------- setup ----------------

    def _init_positions(self) -> None:
        n = self.wcfg.n_nodes
        L = self.wcfg.road_length_m
        # Deterministic spread across the road (positions depend only on n).
        self.positions = [L * (i + 0.5) / n for i in range(n)]
        speeds = [self.wcfg.speed_mean_mps + self.wcfg.speed_jitter_mps * self.rng.random()
                  for _ in range(n)]
        for node, pos, v in zip(self.nodes, self.positions, speeds):
            node.set_state(distance_m=L, speed_mps=v)

    def _schedule_next_emergency(self, now_ms: float) -> None:
        lam = self.wcfg.emergency_lambda
        dt_s = self.wcfg.dt_ms / 1000.0
        # Exponential inter-arrival sampling via inverse transform (deterministic).
        u = self.rng.random()
        if u <= 0.0:
            u = 1e-12
        self._next_emergency_ms = now_ms + (-math.log(1.0 - u) / lam) * 1000.0

    # ---------------- main loop ----------------

    def run(self, event_log: list | None = None) -> WorldMetrics:
        w = self.wcfg
        self._init_positions()
        if w.emergency_enabled:
            self._schedule_next_emergency(0.0)

        m = WorldMetrics()
        now_ms = 0.0
        end_ms = w.duration_s * 1000.0

        while now_ms < end_ms:
            # 1. Emergency injection (Poisson arrivals)
            if w.emergency_enabled and self._next_emergency_ms is not None \
                    and now_ms >= self._next_emergency_ms:
                nid = self.rng.randint(1, w.n_nodes)
                node = self.nodes[nid - 1]
                node.state.brake_active = True
                self.emergencies.append(EmergencyEvent(
                    nid, now_ms, now_ms + w.emergency_duration_ms))
                self._emergency_pending_start[nid] = now_ms
                m.events.append(("EMERGENCY_START", nid, now_ms))
                self._schedule_next_emergency(now_ms)

            for emg in self.emergencies:
                if emg.end_ms <= now_ms:
                    self.nodes[emg.node_id - 1].state.brake_active = False
                    m.events.append(("EMERGENCY_END", emg.node_id, now_ms))
            self.emergencies = [e for e in self.emergencies if e.end_ms > now_ms]
            if self.emergencies:
                m.emergency_active_time_ms += w.dt_ms

            # 2. Kinematics: simple forward drift along the road (wrap at ends)
            dt_s = w.dt_ms / 1000.0
            for idx, node in enumerate(self.nodes):
                if not node.state.brake_active:
                    self.positions[idx] += node.state.speed_mps * dt_s
                    if self.positions[idx] > w.road_length_m:
                        self.positions[idx] = 0.0

            # 3. Transmission phase
            for idx, node in enumerate(self.nodes):
                neighbor_count = self._neighbors_in_range(idx)
                pkt = node.maybe_transmit(now_ms, neighbor_count)
                if pkt is None:
                    continue
                self._deliver(idx, node, pkt, now_ms, m, event_log)

            # 4. ACK processing (ACKs generated at end of previous tick arrive here)
            self._process_acks(now_ms, m)

            # 5. Expire stale pending ACKs
            for node in self.nodes:
                node.expire_pending_acks(now_ms)

            now_ms += w.dt_ms

        return m

    # ---------------- helpers ----------------

    def _neighbors_in_range(self, idx: int) -> int:
        me = self.positions[idx]
        r = self.wcfg.comm_range_m
        return sum(1 for j, p in enumerate(self.positions)
                   if j != idx and abs(p - me) <= r)

    def _deliver(self, idx: int, node: VehicleNode, pkt: P.V2VPacket,
                 now_ms: float, m: WorldMetrics, event_log: list | None) -> None:
        """One frame offered on the shared medium; in-range receivers get it
        if the channel delivers it. ACKs flow back independently."""
        res = self.channel.transmit(P.V2V_PACKET_SIZE, now_ms)
        m.frames_offered += 1
        m.bytes_tx += P.V2V_PACKET_SIZE
        is_emg = pkt.is_safety_critical()

        if is_emg:
            m.emergency_frames_offered += 1
            m.emergency_one_way_ms.append(res.one_way_delay_ms)
            # Preemption latency: emergency-trigger-to-airtime-completion.
            if pkt.sender_id in self._emergency_pending_start:
                preempt_ms = (now_ms + res.one_way_delay_ms) - self._emergency_pending_start.pop(pkt.sender_id)
                m.emergency_first_airtime_ms.append(max(0.0, preempt_ms))
        else:
            m.normal_frames_offered += 1

        if event_log is not None:
            event_log.append([
                int(now_ms), pkt.sender_id, pkt.seq_num,
                P.PRIORITY_NAMES[pkt.priority],
                f"{res.one_way_delay_ms:.3f}",
                1 if res.delivered else 0,
                1 if is_emg else 0,
            ])

        if not res.delivered:
            return
        m.frames_delivered += 1
        if is_emg:
            m.emergency_frames_delivered += 1
        else:
            m.normal_frames_delivered += 1

        # Receivers in range ingest + ACK
        r = self.wcfg.comm_range_m
        me = self.positions[idx]
        for j, other in enumerate(self.nodes):
            if j == idx or abs(self.positions[j] - me) > r:
                continue
            other.on_receive(pkt, now_ms)
            if self.trust_gate is not None:
                d = self.trust_gate.ingest(pkt, now_ms)
                m.gate_accepted += 1 if d.accepted else 0
                m.gate_rejected += 1 if d.rejected else 0
                m.gate_downweighted += 1 if d.downweighted else 0
            ack = other.make_ack(pkt, now_ms + res.one_way_delay_ms)
            m.acks_generated += 1
            # ACK return leg: subject to independent loss
            ack_res = self.channel.transmit(P.V2V_PACKET_SIZE,
                                            now_ms + res.one_way_delay_ms)
            if ack_res.delivered:
                m.acks_received += 1
                # Sender-side pairing happens in the ACK phase; queue it.
                self._ack_queue.append((pkt.sender_id, pkt.seq_num,
                                        now_ms + res.one_way_delay_ms + ack_res.one_way_delay_ms,
                                        is_emg))

    def _process_acks(self, now_ms: float, m: WorldMetrics) -> None:
        due = [a for a in self._ack_queue if a[2] <= now_ms]
        self._ack_queue = [a for a in self._ack_queue if a[2] > now_ms]
        for sender_id, seq, arrival_ms, is_emg in due:
            node = self.nodes[sender_id - 1]
            rtt = node.on_ack(seq, arrival_ms)
            if rtt is None:
                continue
            m.rtt_samples_ms.append(rtt)
            if is_emg:
                m.emergency_rtt_samples_ms.append(rtt)
            else:
                m.normal_rtt_samples_ms.append(rtt)
