#!/usr/bin/env python3
"""F1 — Perception degradation: local vs V2V vs confidence fusion.

Modality: SIMULATION (research EXPERIMENT_SPEC.md section 2.2; seeds 2001-2020).

One ego vehicle; an obstacle vehicle approaches head-on at v_rel. Four
visibility tiers set the local sensor max range: Clear 100 m -> 40 m sensor,
Light dust 50 m -> 20 m, Moderate fog 20 m -> 8 m, Dense fog 5 m -> 4 m.
Remote V2V distance = true distance + Gaussian noise (sigma in {0.5, 2, 5} m)
within a 50 m V2X range, message age 100 ms.

Baselines:
  A local only       est = local distance (invisible beyond sensor range)
  B raw V2V only     est = remote noisy distance, accepted unconditionally
  C proposed fusion  confidence F(C_local, C_remote) * exp(-lambda * age)
                     with trust-gate freshness/plausibility

Alarm criterion (ego HMI): estimated distance <= 25 m stopping envelope.
FNR: no alarm before true distance < 20 m. FPR: alarm while true > 25 m.

Usage:
  python3 experiments/sim_f1_perception_fusion.py
"""

import json
import math
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl import packet as P
from daas_impl.simio import RunContext, repo_root, write_checksum_manifest
from daas_impl.trust_gate import TrustGate, TrustGateConfig
from daas_impl.world import percentile

RAW_HEADER = ["run_id", "seed", "visibility_tier", "visibility_m",
              "approach_speed_mps", "noise_sigma_m", "method",
              "warning_distance_m", "lead_time_s", "false_positive",
              "false_negative", "alarm_toggles", "v2v_in_range",
              "valid_info_fraction"]

TIERS = [("clear", 100.0), ("light_dust", 50.0), ("moderate_fog", 20.0),
         ("dense_fog", 5.0)]
SPEEDS = [5.0, 10.0, 15.0]
SIGMAS = [0.5, 2.0, 5.0]
SEEDS = list(range(2001, 2021))     # 20 runs per tier
D0_M = 60.0                          # obstacle starts beyond V2X range
LOCAL_RANGE_CLEAR_M = 40.0
LOCAL_RANGE_FOG_M = 4.0
V2X_RANGE_M = 50.0
STOP_DIST_M = 25.0
FNR_DIST_M = 20.0
LAMBDA_PER_MS = 0.005
MSG_AGE_MS = 100.0
DT_MS = 10.0
METHODS = ["local", "v2v", "fusion"]


def local_range_for(visibility_m: float) -> float:
    return max(LOCAL_RANGE_FOG_M, LOCAL_RANGE_CLEAR_M * visibility_m / 100.0)


def run_trial(rng: random.Random, method: str, local_range: float,
              speed: float, sigma: float):
    """Simulate one approach. Returns metrics dict."""
    d = D0_M
    v2v_seq = 0
    gate = TrustGate(TrustGateConfig())
    alarm_active = False
    first_alarm_dist = None
    toggles = 0
    false_positive = 0
    false_negative = 0
    fnr_checked = False
    v2v_in_range_steps = 0
    valid_info_steps = 0
    steps = 0
    last_remote = None
    last_remote_age_ms = None

    t_ms = 0.0
    while d > -5.0 and t_ms < 30000.0:
        steps += 1
        # ---- remote V2V update (100 ms cadence) ----
        if (t_ms % MSG_AGE_MS) < DT_MS and d <= V2X_RANGE_M:
            v2v_seq += 1
            v2v_in_range_steps += 1
            noisy = d + rng.gauss(0.0, sigma)
            pkt = P.V2VPacket(sender_id=9, seq_num=v2v_seq,
                              timestamp_ms=int(t_ms), distance_m=max(0.0, noisy),
                              speed_mps=speed).sign()
            dec = gate.ingest(pkt, int(t_ms + MSG_AGE_MS))
            if dec.accepted:
                last_remote = max(0.0, noisy)
                last_remote_age_ms = MSG_AGE_MS
                valid_info_steps += 1

        # ---- per-method estimated distance ----
        local_valid = d <= local_range
        if method == "local":
            est = d if local_valid else None
            conf = 1.0 if local_valid else 0.0
        elif method == "v2v":
            est = last_remote
            conf = 1.0 if last_remote is not None else 0.0
        else:  # fusion
            c_local = 1.0 if local_valid else 0.0
            c_remote = (0.9 if last_remote is not None else 0.0)
            age = last_remote_age_ms if last_remote_age_ms is not None else 10**9
            conf = max(c_local, c_remote) * math.exp(-LAMBDA_PER_MS * age)
            if c_local > 0:
                est = d            # local preempts in near field
            elif last_remote is not None and conf > 0.3:
                est = last_remote
            else:
                est = None
        if est is not None:
            valid_info_steps += 1

        # ---- alarm criterion ----
        want_alarm = est is not None and est <= STOP_DIST_M
        if want_alarm and not alarm_active:
            toggles += 1
            if first_alarm_dist is None:
                first_alarm_dist = d
            if d > STOP_DIST_M + 2.0:      # alarm with no obstacle near stop dist
                false_positive = 1
        if alarm_active and not want_alarm:
            toggles += 1
        alarm_active = want_alarm

        if d < FNR_DIST_M and first_alarm_dist is None:
            false_negative = 1
            fnr_checked = True

        d -= speed * (DT_MS / 1000.0)
        t_ms += DT_MS

    lead = (first_alarm_dist / speed) if first_alarm_dist is not None else None
    return {
        "warning_distance_m": round(first_alarm_dist, 3) if first_alarm_dist is not None else "",
        "lead_time_s": round(lead, 4) if lead is not None else "",
        "false_positive": false_positive,
        "false_negative": false_negative,
        "alarm_toggles": toggles,
        "v2v_in_range": v2v_in_range_steps,
        "valid_info_fraction": round(valid_info_steps / max(2 * steps, 1), 4),
    }


def main() -> int:
    rows: list = []
    by_key: dict = {}

    run = RunContext(
        experiment_id="F1", run_id="F1_fusion", seed=min(SEEDS), run_number=1,
        configuration={
            "tiers": {n: v for n, v in TIERS},
            "speeds_mps": SPEEDS, "sigmas_m": SIGMAS, "seeds": SEEDS,
            "d0_m": D0_M, "local_range_clear_m": LOCAL_RANGE_CLEAR_M,
            "local_range_fog_m": LOCAL_RANGE_FOG_M, "v2x_range_m": V2X_RANGE_M,
            "stop_dist_m": STOP_DIST_M, "fnr_dist_m": FNR_DIST_M,
            "lambda_per_ms": LAMBDA_PER_MS, "msg_age_ms": MSG_AGE_MS,
            "dt_ms": DT_MS, "methods": METHODS,
            "fusion_rule": "max(C_local, 0.9*C_remote)*exp(-0.005*age); local preempts near field",
            "alarm_criterion": "estimated distance <= 25 m stopping envelope",
            "modality": "SIMULATION",
        },
        raw_csv="results/raw/F1_fusion_raw.csv",
    )
    run.ensure_header(RAW_HEADER)

    for tier_name, vis in TIERS:
        lr = local_range_for(vis)
        for i, seed in enumerate(SEEDS):
            speed = SPEEDS[i % len(SPEEDS)]
            sigma = SIGMAS[(i // len(SPEEDS)) % len(SIGMAS)]
            rng = random.Random(seed)
            for method in METHODS:
                res = run_trial(rng, method, lr, speed, sigma)
                row = [f"F1_{tier_name}_{method}_seed{seed}", seed, tier_name,
                       vis, speed, sigma, method, res["warning_distance_m"],
                       res["lead_time_s"], res["false_positive"],
                       res["false_negative"], res["alarm_toggles"],
                       res["v2v_in_range"], res["valid_info_fraction"]]
                rows.append(row)
                run.append_rows(RAW_HEADER, [row])
                by_key.setdefault((tier_name, method), []).append(res)
        print(f"[F1] tier={tier_name}: 20 runs x 3 methods done")
    run.finalize()

    # ---- derived summary ----
    def agg(res_list, key):
        vals = [r[key] for r in res_list if isinstance(r[key], (int, float))]
        if not vals:
            return {"mean": None, "std": None, "n": 0}
        return {"mean": round(statistics.mean(vals), 4),
                "std": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
                "n": len(vals)}

    summary = {"experiment_id": "F1", "modality": "SIMULATION", "seeds": SEEDS,
               "note": "SIMULATION model with surrogate sensors; NOT field data",
               "tiers": {}}
    for (tier, method), res_list in sorted(by_key.items()):
        summary["tiers"].setdefault(tier, {})[method] = {
            "warning_distance_m": agg(res_list, "warning_distance_m"),
            "lead_time_s": agg(res_list, "lead_time_s"),
            "false_positive_rate_pct": round(100.0 * sum(r["false_positive"] for r in res_list)
                                             / len(res_list), 3),
            "false_negative_rate_pct": round(100.0 * sum(r["false_negative"] for r in res_list)
                                             / len(res_list), 3),
            "alarm_toggles_mean": agg(res_list, "alarm_toggles"),
            "valid_info_fraction": agg(res_list, "valid_info_fraction"),
        }

    dpath = os.path.join(repo_root(), "results", "derived")
    os.makedirs(dpath, exist_ok=True)
    with open(os.path.join(dpath, "F1_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    write_checksum_manifest()

    for tier, _ in TIERS:
        t = summary["tiers"][tier]
        print(f"[F1] {tier}: warn_dist local={t['local']['warning_distance_m']['mean']} "
              f"v2v={t['v2v']['warning_distance_m']['mean']} "
              f"fusion={t['fusion']['warning_distance_m']['mean']} m | "
              f"FNR fusion={t['fusion']['false_negative_rate_pct']}%")
    print("F1: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
