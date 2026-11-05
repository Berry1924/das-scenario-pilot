"""ESP-NOW channel model for discrete-event simulation.

SIMULATION ONLY — this models a 2.4 GHz ESP-NOW link (802.11b action frames,
1 Mbps PHY) with configurable per-frame delay, random loss, burst loss,
blackout windows, and CSMA contention. It is NOT C-V2X or DSRC and does not
model fog-specific RF impairment (per CLM-14, sub-6 GHz fog attenuation is
negligible; the mine impediment is optical, not RF absorption).

All durations are in milliseconds of simulated time. A single RNG instance is
injected so runs are deterministic under a fixed seed.
"""

import math
from dataclasses import dataclass, field


@dataclass
class ChannelConfig:
    base_delay_ms: float = 2.0          # uncongested one-way airtime + processing
    delay_jitter_ms: float = 1.0        # uniform jitter on one-way delay
    phy_rate_mbps: float = 1.0          # ESP-NOW 802.11b action frames
    packet_bytes: int = 32
    tx_power_dbm_bench: float = 0.0
    tx_power_dbm_sim: float = 20.0
    loss_prob: float = 0.0              # i.i.d. drop probability per frame
    burst_loss_len: int = 0             # >0 activates burst-loss mode
    blackout_start_ms: float | None = None
    blackout_end_ms: float | None = None
    congestion_loss_slope: float = 0.0  # extra loss per offered frame in window
    window_ms: float = 10.0             # contention accounting window
    max_frames_per_window: int = 10**9  # saturation cap (frames per window)


@dataclass
class TransmitResult:
    delivered: bool
    one_way_delay_ms: float
    rtt_ms: float | None
    ack_delivered: bool


class ChannelModel:
    """Shared-lossy-medium model. Offered frames consume window capacity."""

    def __init__(self, cfg: ChannelConfig, rng):
        self.cfg = cfg
        self.rng = rng
        self.offered_in_window: list[float] = []
        self.total_offered = 0
        self.total_delivered = 0
        self._burst_remaining = 0

    def _window_capacity_available(self, now_ms: float) -> bool:
        w = self.cfg.window_ms
        self.offered_in_window = [t for t in self.offered_in_window if now_ms - t < w]
        return len(self.offered_in_window) < self.cfg.max_frames_per_window

    def _in_blackout(self, now_ms: float) -> bool:
        s, e = self.cfg.blackout_start_ms, self.cfg.blackout_end_ms
        if s is None or e is None:
            return False
        return s <= now_ms < e

    def transmit(self, pkt_size_bytes: int, now_ms: float) -> TransmitResult:
        """Attempt delivery of one frame at simulated time now_ms."""
        self.total_offered += 1
        self.offered_in_window.append(now_ms)

        airtime_ms = (pkt_size_bytes * 8.0) / (self.cfg.phy_rate_mbps * 1000.0)
        delay = self.cfg.base_delay_ms + airtime_ms + self.cfg.delay_jitter_ms * self.rng.random()

        if self._in_blackout(now_ms):
            return TransmitResult(False, delay, None, False)

        if self.cfg.burst_loss_len > 0:
            if self._burst_remaining > 0:
                self._burst_remaining -= 1
                return TransmitResult(False, delay, None, False)
            if self.rng.random() < self.cfg.loss_prob:
                self._burst_remaining = self.cfg.burst_loss_len - 1
                return TransmitResult(False, delay, None, False)
        else:
            if self.rng.random() < self.cfg.loss_prob:
                return TransmitResult(False, delay, None, False)

        if not self._window_capacity_available(now_ms):
            return TransmitResult(False, delay, None, False)

        self.total_delivered += 1
        rtt = 2.0 * delay + airtime_ms + self.cfg.delay_jitter_ms * self.rng.random()
        return TransmitResult(True, delay, rtt, True)

    def reset_burst(self) -> None:
        self._burst_remaining = 0
