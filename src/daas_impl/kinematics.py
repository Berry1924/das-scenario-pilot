"""Relative kinematics for leader/follower mine haul-road scenarios.

Deterministic ground-truth trajectories with an RNG available for any
stochastic perturbations. Used by VS6 integration, T1 (message age vs TTC
error) and F1 (perception fusion) experiment runners.
"""

import math
from dataclasses import dataclass


@dataclass
class LeadFollowConfig:
    lead_speed0_mps: float = 10.0     # initial leader speed
    follow_speed0_mps: float = 10.0   # initial follower speed
    headway_m: float = 50.0           # initial separation
    brake_start_s: float = 5.0        # when the leader starts braking
    lead_accel_mps2: float = 0.0      # cruise accel (usually 0)
    lead_brake_accel_mps2: float = -4.0  # deceleration during braking
    v_min_mps: float = 0.0            # speeds are clamped >= 0


@dataclass
class LeadFollowTrajectory:
    cfg: LeadFollowConfig

    def leader_state_at(self, t_s: float) -> tuple[float, float]:
        """Returns (lead_speed_mps, lead_position_gain_m) at time t.

        Position is gain relative to origin (leader starts at 0 with initial
        headway factored separately).
        """
        c = self.cfg
        if t_s < c.brake_start_s:
            v = c.lead_speed0_mps + c.lead_accel_mps2 * t_s
            x = c.lead_speed0_mps * t_s + 0.5 * c.lead_accel_mps2 * t_s * t_s
            return max(v, c.v_min_mps), x
        dt = t_s - c.brake_start_s
        v0 = c.lead_speed0_mps + c.lead_accel_mps2 * c.brake_start_s
        v = v0 + c.lead_brake_accel_mps2 * dt
        if v <= c.v_min_mps:
            # leader stopped: position frozen at stop point
            t_stop = (c.v_min_mps - v0) / c.lead_brake_accel_mps2
            x = (c.lead_speed0_mps * c.brake_start_s
                 + 0.5 * c.lead_accel_mps2 * (c.brake_start_s ** 2)
                 + v0 * t_stop + 0.5 * c.lead_brake_accel_mps2 * (t_stop ** 2))
            return c.v_min_mps, x
        x = (c.lead_speed0_mps * c.brake_start_s
             + 0.5 * c.lead_accel_mps2 * (c.brake_start_s ** 2)
             + v0 * dt + 0.5 * c.lead_brake_accel_mps2 * dt * dt)
        return v, x

    def follower_state_at(self, t_s: float) -> tuple[float, float]:
        """Follower keeps initial speed (non-reactive study dynamics)."""
        c = self.cfg
        v = c.follow_speed0_mps
        x = -c.headway_m + v * t_s   # follower starts headway meters behind
        return v, x

    def separation_at(self, t_s: float) -> float:
        _, xl = self.leader_state_at(t_s)
        _, xf = self.follower_state_at(t_s)
        return xl - xf

    def true_closing_speed_at(self, t_s: float) -> float:
        vl, _ = self.leader_state_at(t_s)
        vf, _ = self.follower_state_at(t_s)
        return vf - vl
