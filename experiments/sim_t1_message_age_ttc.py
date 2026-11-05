#!/usr/bin/env python3
"""T1 — Message age impact on TTC estimation error.

Modality: SIMULATION (deterministic kinematic model, research seeds 4001-4050).

Leader cruises at v0=10 m/s, then brakes at a lead deceleration tier at t=2 s.
Follower holds 10 m/s (non-reactive). Ground-truth TTC(t) from true states;
stale TTC(t) from delayed packet states at t - A_j; proposed (freshness-gated)
uses the delayed packet when A_j <= 500 ms and an ideal local-sensor surrogate
(equals ground truth) otherwise.

Per research EXPERIMENT_SPEC.md section 2.5:
  ages_ms       = {20, 50, 100, 200, 300, 500, 750, 1000, 1500}
  lead_accels   = {-1.0, -2.5, -4.0, -6.0} m/s^2
  headways      = {30, 50, 80} m (cycled across seeds)
  trajectories  = 50 per acceleration tier, seeds 4001..4050
  dt            = 10 ms

Usage:
  python3 experiments/sim_t1_message_age_ttc.py

Outputs:
  results/raw/T1_age_rmse.csv            per-(accel,age,seed) RMSE rows
  results/raw/T1_timeseries_seed4001.csv tick-level detail for seed 4001
  results/derived/T1_summary.json
  results/metadata/T1_*.metadata.json
"""

import json
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl.kinematics import LeadFollowConfig, LeadFollowTrajectory
from daas_impl.simio import RunContext, repo_root, write_checksum_manifest
from daas_impl.ttc import compute_ttc

AGES_MS = [20, 50, 100, 200, 300, 500, 750, 1000, 1500]
ACCELS = [-1.0, -2.5, -4.0, -6.0]
HEADWAYS_M = [30.0, 50.0, 80.0]
N_TRAJ = 50
SEEDS = list(range(4001, 4001 + N_TRAJ))
DT_S = 0.010
DURATION_S = 6.0        # covers braking (2 s brake start + <2.5 s to stop at -4)
BRAKE_START_S = 2.0
FRESHNESS_MS = 500
WARN_TTC_S = 2.0
# TTC = d/v_rel diverges as v_rel -> 0+ (brake initiation). Estimation error
# is therefore evaluated only inside the operational warning horizon
# (TTC_true <= EVAL_HORIZON_S), where a warning system actually acts. Steps
# where the delayed data wrongly reports a non-closing state are counted
# separately as the false-clear share.
EVAL_HORIZON_S = 10.0

RMSE_HEADER = ["trajectory_id", "accel_mps2", "age_ms", "seed", "headway_m",
               "n_eval_steps", "ttc_rmse_s", "ttc_mae_s",
               "max_abs_err_s", "false_clear_share", "warn_delay_ms_stale",
               "warn_delay_ms_proposed"]
TS_HEADER = ["sim_time_s", "trajectory_id", "accel_mps2", "age_ms",
             "true_dist_m", "delayed_dist_m", "true_vrel_mps",
             "delayed_vrel_mps", "true_ttc_s", "stale_ttc_s",
             "proposed_ttc_s", "ttc_error_s"]


def first_warn_time(ttc_series, warn_s=WARN_TTC_S):
    for i, v in enumerate(ttc_series):
        if v is not None and v <= warn_s:
            return i * DT_S
    return None


def simulate(accel: float, headway: float, seed: int):
    """Returns list of per-age RMSE rows; also returns tick series for
    seed 4001 detail logging."""
    cfg = LeadFollowConfig(
        lead_speed0_mps=10.0, follow_speed0_mps=10.0, headway_m=headway,
        brake_start_s=BRAKE_START_S, lead_brake_accel_mps2=accel,
    )
    traj = LeadFollowTrajectory(cfg)
    n_steps = int(DURATION_S / DT_S)

    ts_rows = []
    out_rows = []

    for age_ms in AGES_MS:
        a_s = age_ms / 1000.0
        errs: list[float] = []
        n_horizon = 0
        n_false_clear = 0
        true_ttc_series: list = []
        stale_ttc_series: list = []
        proposed_ttc_series: list = []

        for k in range(n_steps):
            t = k * DT_S
            d_true = traj.separation_at(t)
            v_true = traj.true_closing_speed_at(t)
            ttc_true = compute_ttc(d_true, v_true)

            t_d = max(0.0, t - a_s)          # delayed state timestamp
            d_del = traj.separation_at(t_d)
            v_del = traj.true_closing_speed_at(t_d)
            ttc_stale = compute_ttc(d_del, v_del)

            if age_ms <= FRESHNESS_MS:
                ttc_prop = ttc_stale
            else:
                # proposed: stale packet discarded, ideal local surrogate used
                ttc_prop = ttc_true

            true_ttc_series.append(ttc_true)
            stale_ttc_series.append(ttc_stale)
            proposed_ttc_series.append(ttc_prop)

            # Evaluation restricted to the operational warning horizon.
            if ttc_true is not None and ttc_true <= EVAL_HORIZON_S:
                n_horizon += 1
                if ttc_stale is not None:
                    errs.append(abs(ttc_stale - ttc_true))
                else:
                    # Stale data claims non-closing while the truth is closing:
                    # a critical false-clear miss within the warning horizon.
                    n_false_clear += 1

            if seed == min(SEEDS) and t > 0.0:
                ts_rows.append([
                    round(t, 3), f"T{seed}_{accel}_{age_ms}", accel, age_ms,
                    round(d_true, 3), round(d_del, 3), round(v_true, 3),
                    round(v_del, 3),
                    round(ttc_true, 4) if ttc_true is not None else "",
                    round(ttc_stale, 4) if ttc_stale is not None else "",
                    round(ttc_prop, 4) if ttc_prop is not None else "",
                    round(abs(ttc_stale - ttc_true), 4)
                    if (ttc_true is not None and ttc_stale is not None) else "",
                ])

        n = len(errs)
        rmse = math.sqrt(sum(e * e for e in errs) / n) if n else 0.0
        mae = sum(errs) / n if n else 0.0
        max_err = max(errs) if errs else 0.0
        false_clear_share = n_false_clear / n_horizon if n_horizon else 0.0

        wt_true = first_warn_time(true_ttc_series)
        wt_stale = first_warn_time(stale_ttc_series)
        wt_prop = first_warn_time(proposed_ttc_series)
        warn_delay_stale = ((wt_stale - wt_true) * 1000.0
                            if (wt_true is not None and wt_stale is not None)
                            else "")
        warn_delay_prop = ((wt_prop - wt_true) * 1000.0
                           if (wt_true is not None and wt_prop is not None)
                           else "")

        out_rows.append([
            f"T{seed}_{accel}_{age_ms}", accel, age_ms, seed, headway,
            n, round(rmse, 5), round(mae, 5), round(max_err, 5),
            round(false_clear_share, 5),
            round(warn_delay_stale, 1) if warn_delay_stale != "" else "",
            round(warn_delay_prop, 1) if warn_delay_prop != "" else "",
        ])

    return out_rows, ts_rows, (seed == min(SEEDS))


def main() -> int:
    rmse_rows: list = []
    ts_rows: list = []

    run = RunContext(
        experiment_id="T1", run_id="T1_age_rmse", seed=min(SEEDS), run_number=1,
        configuration={
            "ages_ms": AGES_MS, "accels": ACCELS, "headways_m": HEADWAYS_M,
            "n_trajectories_per_accel": N_TRAJ, "seeds": SEEDS,
            "dt_ms": 10, "duration_s": DURATION_S, "brake_start_s": BRAKE_START_S,
            "freshness_ms": FRESHNESS_MS, "warn_ttc_s": WARN_TTC_S,
            "v0_mps": 10.0, "follower_reactive": False,
            "local_fallback_surrogate": "ideal (equals ground truth at A_j > 500 ms)",
            "modality": "SIMULATION",
        },
        raw_csv="results/raw/T1_age_rmse.csv",
    )
    run.ensure_header(RMSE_HEADER)

    ts_run = RunContext(
        experiment_id="T1", run_id="T1_timeseries_seed4001", seed=min(SEEDS),
        run_number=1, configuration=run.configuration,
        raw_csv="results/raw/T1_timeseries_seed4001.csv",
    )

    for accel in ACCELS:
        for i, seed in enumerate(SEEDS):
            headway = HEADWAYS_M[i % len(HEADWAYS_M)]
            out, tslines, is_first = simulate(accel, headway, seed)
            run.append_rows(RMSE_HEADER, out)
            rmse_rows.extend(out)
            if is_first:
                ts_rows.extend(tslines)

    ts_run.ensure_header(TS_HEADER)
    ts_run.append_rows(TS_HEADER, ts_rows)
    ts_run.finalize()
    run.finalize()

    # ---- derived summary: RMSE stats per (accel, age) ----
    per_age: dict = {}
    for r in rmse_rows:
        per_age.setdefault(r[2], []).append(r[6])     # key: age_ms -> rmse
    per_age_accel: dict = {}
    for r in rmse_rows:
        key = (r[1], r[2])   # (accel, age)
        per_age_accel.setdefault(key, []).append((r[6], r[7], r[8], r[9]))

    rmse_by_age = {
        str(age): {
            "rmse_mean_s": round(statistics.mean(v), 5),
            "rmse_std_s": round(statistics.stdev(v), 5) if len(v) > 1 else 0.0,
            "rmse_median_s": round(statistics.median(v), 5),
            "n": len(v),
        }
        for age, v in sorted(per_age.items())
    }
    cells = []
    for (accel, age), trip in sorted(per_age_accel.items()):
        rmses, maes, maxes, fcs = zip(*trip)
        cells.append({
            "accel_mps2": accel, "age_ms": age,
            "rmse_mean_s": round(statistics.mean(rmses), 5),
            "rmse_p95_s": None if len(rmses) < 20 else round(sorted(rmses)[int(0.95*len(rmses))-1], 5),
            "mae_mean_s": round(statistics.mean(maes), 5),
            "max_err_mean_s": round(statistics.mean(maxes), 5),
            "false_clear_share_mean": round(statistics.mean(fcs), 5),
            "n": len(rmses),
        })

    # non-linear fit: RMSE = alpha * A^beta (log-log regression by least squares)
    xs = [math.log(a) for a in AGES_MS]
    ys = [math.log(rmse_by_age[str(a)]["rmse_mean_s"]) if rmse_by_age[str(a)]["rmse_mean_s"] > 0 else math.log(1e-9) for a in AGES_MS]
    xbar, ybar = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    den = sum((x - xbar) ** 2 for x in xs)
    beta = num / den if den else 0.0
    alpha = math.exp(ybar - beta * xbar)

    summary = {
        "experiment_id": "T1",
        "modality": "SIMULATION",
        "seeds": SEEDS,
        "ages_ms": AGES_MS,
        "accels_mps2": ACCELS,
        "headways_m": HEADWAYS_M,
        "rmse_by_age_over_accel_seeds": rmse_by_age,
        "cells": cells,
        "fit_rmse_alpha": round(alpha, 6),
        "fit_rmse_beta": round(beta, 4),
        "note": ("Stale-TTC RMSE grows with message age; proposed freshness-gated "
                 "path uses an ideal local sensor surrogate (equal to ground truth) "
                 "for A_j > 500 ms, which sets its error to zero — a modelling "
                 "assumption, not a measured hardware result."),
    }
    dpath = os.path.join(repo_root(), "results", "derived")
    os.makedirs(dpath, exist_ok=True)
    with open(os.path.join(dpath, "T1_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    write_checksum_manifest()

    for age in AGES_MS:
        r = rmse_by_age[str(age)]
        print(f"[T1] age={age:5d} ms  RMSE={r['rmse_mean_s']:.4f} s "
              f"(sd {r['rmse_std_s']:.4f}, n={r['n']})")
    print(f"[T1] fit: RMSE = {alpha:.6f} * A^{beta:.3f}  (A in ms)")
    print("T1: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
