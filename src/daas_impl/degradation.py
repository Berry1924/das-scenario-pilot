"""Graceful degradation state machine — VS5.

States: FULL, V2V_DEGRADED, SENSOR_DEGRADED, BOTH_DEGRADED.
Mirrors the firmware fallback_manager (2500 ms peer-silence watchdog) and
hazard_state (1500 ms anti-flicker latch) semantics.

Transitions:
  FULL -> V2V_DEGRADED        peer silence >= watchdog timeout (V2V outage)
  FULL -> SENSOR_DEGRADED     local sensor dropout while V2V healthy
  V2V_DEGRADED / SENSOR_DEGRADED -> BOTH_DEGRADED  second subsystem fails
  *_DEGRADED -> FULL          trigger recovered (communication recovery /
                              sensor recovery), no hysteresis by default
"""

import math
from dataclasses import dataclass, field

FULL = "FULL"
V2V_DEGRADED = "V2V_DEGRADED"
SENSOR_DEGRADED = "SENSOR_DEGRADED"
BOTH_DEGRADED = "BOTH_DEGRADED"
ALL_STATES = (FULL, V2V_DEGRADED, SENSOR_DEGRADED, BOTH_DEGRADED)

DEFAULT_WATCHDOG_MS = 2500.0
DEFAULT_HAZARD_LATCH_MS = 1500.0
DEFAULT_SENSOR_FRESH_MS = 500.0


@dataclass
class DegradationConfig:
    watchdog_ms: float = DEFAULT_WATCHDOG_MS
    hazard_latch_ms: float = DEFAULT_HAZARD_LATCH_MS
    sensor_fresh_ms: float = DEFAULT_SENSOR_FRESH_MS


@dataclass
class DegradationEvent:
    timestamp_ms: float
    state: str
    trigger: str


@dataclass
class DegradationMonitor:
    """Tracks subsystem health and emits state transitions + latch behaviour."""

    cfg: DegradationConfig = field(default_factory=DegradationConfig)
    state: str = FULL
    last_peer_heartbeat_ms: float | None = None
    last_sensor_ok_ms: float | None = None
    hazard_latch_until_ms: float = -1.0
    events: list[DegradationEvent] = field(default_factory=list)
    time_in_state_ms: dict = field(default_factory=lambda: {s: 0.0 for s in ALL_STATES})
    fallback_triggers: int = 0
    recoveries: int = 0
    _last_eval_ms: float | None = None

    def record_peer_heartbeat(self, now_ms: float) -> None:
        self.last_peer_heartbeat_ms = now_ms

    def record_sensor_ok(self, now_ms: float) -> None:
        self.last_sensor_ok_ms = now_ms

    def latch_hazard(self, now_ms: float) -> None:
        self.hazard_latch_until_ms = max(self.hazard_latch_until_ms,
                                         now_ms + self.cfg.hazard_latch_ms)

    def hazard_latch_active(self, now_ms: float) -> bool:
        return now_ms < self.hazard_latch_until_ms

    def _transition(self, now_ms: float, new_state: str, trigger: str) -> None:
        if new_state != self.state:
            self.events.append(DegradationEvent(now_ms, new_state, trigger))
            if "DEGRADED" in new_state and "DEGRADED" not in self.state:
                self.fallback_triggers += 1
            if new_state == FULL:
                self.recoveries += 1
            self.state = new_state

    def update(self, now_ms: float, v2v_healthy: bool | None = None,
               sensor_healthy: bool | None = None) -> str:
        """Recompute state at simulated time now_ms.

        v2v_healthy/sensor_healthy may be passed explicitly (test hook);
        otherwise derived from heartbeat/sensor freshness timers.
        """
        if self._last_eval_ms is not None:
            delta = now_ms - self._last_eval_ms
            if delta > 0:
                self.time_in_state_ms[self.state] += delta
        self._last_eval_ms = now_ms

        if v2v_healthy is None:
            v2v_healthy = (
                self.last_peer_heartbeat_ms is not None
                and (now_ms - self.last_peer_heartbeat_ms) <= self.cfg.watchdog_ms
            )
        if sensor_healthy is None:
            sensor_healthy = (
                self.last_sensor_ok_ms is not None
                and (now_ms - self.last_sensor_ok_ms) <= self.cfg.sensor_fresh_ms
            )

        if v2v_healthy and sensor_healthy:
            self._transition(now_ms, FULL, "both_subsystems_healthy")
        elif v2v_healthy and not sensor_healthy:
            self._transition(now_ms, SENSOR_DEGRADED, "sensor_dropout")
        elif not v2v_healthy and sensor_healthy:
            self._transition(now_ms, V2V_DEGRADED, "peer_silence_watchdog")
        else:
            self._transition(now_ms, BOTH_DEGRADED, "both_subsystems_unhealthy")
        return self.state

    def reset(self) -> None:
        self.state = FULL
        self.last_peer_heartbeat_ms = None
        self.last_sensor_ok_ms = None
        self.hazard_latch_until_ms = -1.0
        self.events.clear()
        self.time_in_state_ms = {s: 0.0 for s in ALL_STATES}
        self.fallback_triggers = 0
        self.recoveries = 0
        self._last_eval_ms = None
