"""TTC / risk logic — VS4.

Piecewise TTC definition (matches the corrected manuscript equation and the
firmware risk engine semantics):

    TTC = d / v_rel   if v_rel > eps     (closing)
    TTC = inf         otherwise          (non-closing / diverging / zero)

with a configurable epsilon guard (default 0.001 m/s from EXPERIMENT_SPEC.md).
Risk thresholds (distance and TTC) are configurable engineering values carried
over from node_config.h; they are NOT certified values.
"""

import math
from dataclasses import dataclass

from .packet import (
    RISK_LEVEL_SAFE, RISK_LEVEL_CAUTION, RISK_LEVEL_WARNING, RISK_LEVEL_CRITICAL,
)

DEFAULT_TTC_EPS_MPS = 0.001


@dataclass
class RiskThresholds:
    dist_critical_m: float = 4.0
    dist_warning_m: float = 8.0
    dist_caution_m: float = 15.0
    ttc_critical_s: float = 1.5
    ttc_warning_s: float = 3.0
    ttc_caution_s: float = 5.0


@dataclass
class RiskAssessment:
    ttc_s: float | None            # None == non-closing state (TTC = infinity)
    risk_level: int
    imminent_collision: bool
    distance_m: float
    v_rel_mps: float


def compute_ttc(distance_m: float, v_rel_mps: float,
                eps: float = DEFAULT_TTC_EPS_MPS) -> float | None:
    """Return TTC in seconds, or None for a non-closing state (TTC = infinity).

    v_rel is the closing speed (positive = gap shrinking).
    """
    if distance_m is None or not math.isfinite(distance_m) or distance_m < 0.0:
        return None
    if v_rel_mps is None or not math.isfinite(v_rel_mps):
        return None
    if v_rel_mps > eps:
        return distance_m / v_rel_mps
    return None


def assess_risk(distance_m: float, v_rel_mps: float, thresholds: RiskThresholds,
                eps: float = DEFAULT_TTC_EPS_MPS,
                brake_active: bool = False) -> RiskAssessment:
    """Risk assessment. Invalid distance (negative / non-finite) means 'no
    ranging information' — it does NOT escalate distance-based risk (no-info
    is not danger); emergency escalation then comes from brake_active only."""
    ttc = compute_ttc(distance_m, v_rel_mps, eps)

    if ttc is not None and ttc <= thresholds.ttc_critical_s:
        level = RISK_LEVEL_CRITICAL
    elif ttc is not None and ttc <= thresholds.ttc_warning_s:
        level = RISK_LEVEL_WARNING
    elif ttc is not None and ttc <= thresholds.ttc_caution_s:
        level = RISK_LEVEL_CAUTION
    else:
        level = RISK_LEVEL_SAFE

    valid_distance = (distance_m is not None and math.isfinite(distance_m)
                      and distance_m >= 0.0)
    if valid_distance:
        if distance_m <= thresholds.dist_critical_m:
            level = RISK_LEVEL_CRITICAL
        elif distance_m <= thresholds.dist_warning_m and level < RISK_LEVEL_WARNING:
            level = RISK_LEVEL_WARNING
        elif distance_m <= thresholds.dist_caution_m and level < RISK_LEVEL_CAUTION:
            level = RISK_LEVEL_CAUTION

    if brake_active:
        level = RISK_LEVEL_CRITICAL

    return RiskAssessment(
        ttc_s=ttc,
        risk_level=level,
        imminent_collision=(level == RISK_LEVEL_CRITICAL),
        distance_m=distance_m,
        v_rel_mps=v_rel_mps,
    )
