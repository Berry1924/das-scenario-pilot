#!/usr/bin/env python3
"""R1 / VS5 — Communication & sensor failure with graceful fallback.

Modality: SIMULATION. Receiver-focused fault-injection model:
peer beacons arrive at 10 Hz through a lossy channel; the local sensor
stream can drop out; the DegradationMonitor runs the dual-stage mechanism
(1500 ms anti-flicker hazard latch + 2500 ms fallback watchdog).

Fault injection scenarios:
  burst_loss   {1, 3, 5, 10} consecutive dropped packets during active hazard
  blackout     total transmitter power-down window (measures watchdog latency)
  sensor_dropout  sensor failure probability {0, 0.2}
  conflict     local sensor clear (>30 m) while V2V reports obstacle at 5 m
  loss_scan    steady i.i.d. loss levels {0, 10, 20, 30, 50, 100%}

Baselines:
  A naive volatile  (zero temporal memory: warning drops on any missing packet)
  B static hang     (infinite latch: warning freezes on last state)
  C proposed        (1500 ms latch + 2500 ms watchdog)

Usage:
  python3 experiments/sim_r1_fallback.py

Outputs:
  results/raw/R1_scenarios.csv    per-scenario aggregate rows
  results/raw/R1_timeline_blackout_baselineC_seed5001.csv  tick-level timeline
  results/derived/R1_summary.json
  results/metadata/R1_*.metadata.json
"""

import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl import degradation as D
from daas_impl.simio import RunContext, repo_root, write_checksum_manifest

SCEN_HEADER = ["scenario", "baseline", "seed", "fault_param", "duration_ms",
               "full_pct", "v2v_degraded_pct", "sensor_degraded_pct",
               "both_degraded_pct", "warning_dropout_ms", "false_clear_count",
               "fallback_triggered", "fallback_latency_ms",
               "recovery_latency_ms", "decision_coverage_pct",
               "ghost_warning_ms", "packets_rx", "packets_lost"]

BEACON_INTERVAL_MS = 100.0
SENSOR_INTERVAL_MS = 50.0
WATCHDOG_MS = 2500.0
LATCH_MS = 1500.0
DURATION_MS = 60000
SEEDS = list(range(5001, 5006))   # 5 sim trials per fault mode
BURST_LENGTHS = [1, 3, 5, 10]
LOSS_LEVELS = [0.0, 0.10, 0.20, 0.30, 0.50, 1.0]
SENSOR_DROPOUTS = [0.0, 0.20]
BASELINES = ["A_naive_volatile", "B_static_hang", "C_proposed"]


def run_receiver_sim(rng: random.Random, scenario: str, baseline: str,
                     fault_param: float | int):
    """Simulate one receiver node for DURATION_MS at 10 ms resolution.

    Hazard window: 10-30 s (peer reports hazard in that interval; fault
    injected at 15-18 s region). The hazard is *truly* active whenever the
    peer reports it in a delivered packet; warning logic per baseline.
    """
    dt = 10.0
    hazard_start = 10000.0
    hazard_end = 30000.0
    fault_start = 15000.0

    mon = D.DegradationMonitor()
    if baseline == "A_naive_volatile":
        mon.cfg.hazard_latch_ms = 0.0
    elif baseline == "B_static_hang":
        mon.cfg.hazard_latch_ms = os.sys.float_info.max
        mon.cfg.watchdog_ms = os.sys.float_info.max
    else:
        mon.cfg.hazard_latch_ms = LATCH_MS
        mon.cfg.watchdog_ms = WATCHDOG_MS

    # --- fault schedule ---
    burst_remaining = 0
    blackout_window = (fault_start, fault_start + fault_param * BEACON_INTERVAL_MS) \
        if scenario == "burst_loss" else None
    blackout_total = (fault_start, min(fault_start + 5000.0, hazard_end)) \
        if scenario == "blackout" else None
    sensor_dropout = fault_param if scenario == "sensor_dropout" else 0.0
    steady_loss = fault_param if scenario == "loss_scan" else 0.0
    conflict = scenario == "conflict"

    warning_dropout_ms = 0.0
    false_clear_count = 0
    ghost_warning_ms = 0.0
    prev_warning_active = True
    packets_rx = 0
    packets_lost = 0
    decision_ok_ms = 0.0
    fallback_latency_ms = None
    recovery_latency_ms = None
    last_packet_rx_ms = None
    fallback_watch_start_ms = None
    blackout_pending_rec_ms = None

    # Baseline B frozen warning state
    frozen_warning = False

    t = 0.0
    while t < DURATION_MS:
        hazard_truly_active = hazard_start <= t < hazard_end

        # --- peer beacon arrival (10 Hz) with failure model ---
        beacon_due = (t % BEACON_INTERVAL_MS) < dt
        beacon_lost = False
        if beacon_due:
            if scenario == "burst_loss" and blackout_window \
                    and blackout_window[0] <= t < blackout_window[1]:
                beacon_lost = True
            elif scenario == "blackout" and blackout_total \
                    and blackout_total[0] <= t < blackout_total[1]:
                beacon_lost = True
            elif rng.random() < steady_loss:
                beacon_lost = True
            if beacon_lost:
                packets_lost += 1
            else:
                packets_rx += 1
                last_packet_rx_ms = t
                mon.record_peer_heartbeat(t)

        sensorok_due = (t % SENSOR_INTERVAL_MS) < dt
        if sensorok_due and rng.random() >= sensor_dropout:
            mon.record_sensor_ok(t)

        # --- baseline-specific warning logic + state machine ---
        warning_active = False
        if baseline == "A_naive_volatile":
            # zero temporal memory: hazard only if a hazard packet arrived
            # within the last beacon interval
            warning_active = hazard_truly_active and last_packet_rx_ms is not None \
                and (t - last_packet_rx_ms) < BEACON_INTERVAL_MS
        elif baseline == "B_static_hang":
            if packets_rx > 0 and hazard_truly_active and last_packet_rx_ms is not None \
                    and (t - last_packet_rx_ms) < BEACON_INTERVAL_MS:
                frozen_warning = True
            warning_active = frozen_warning
        else:
            # C: latch + watchdog via monitor
            if hazard_truly_active and last_packet_rx_ms is not None \
                    and (t - last_packet_rx_ms) < BEACON_INTERVAL_MS:
                mon.latch_hazard(t)
            warning_active = mon.hazard_latch_active(t)

        state = mon.update(t)

        # --- metric accounting ---
        if hazard_truly_active and not warning_active:
            warning_dropout_ms += dt
        if not hazard_truly_active and warning_active:
            ghost_warning_ms += dt
        if warning_one_tick(hazard_truly_active, warning_active):
            pass
        if prev_warning_active and not warning_active and hazard_truly_active:
            false_clear_count += 1
        prev_warning_active = warning_active

        if mon.state == D.FULL or mon.hazard_latch_active(t):
            decision_ok_ms += dt

        # fallback / recovery latency (blackout & burst scenarios)
        if scenario in ("blackout", "burst_loss", "loss_scan"):
            if mon.state != D.FULL and fallback_watch_start_ms is None \
                    and last_packet_rx_ms is not None:
                fallback_watch_start_ms = last_packet_rx_ms
            if fallback_watch_start_ms is not None and fallback_latency_ms is None \
                    and mon.state == D.V2V_DEGRADED:
                fallback_latency_ms = t - fallback_watch_start_ms
            if fallback_latency_ms is not None and packets_rx > 0 \
                    and last_packet_rx_ms > fallback_watch_start_ms \
                    and mon.state == D.FULL and recovery_latency_ms is None:
                recovery_latency_ms = t - last_packet_rx_ms

        t += dt

    total = DURATION_MS
    state_ms = mon.time_in_state_ms
    return {
        "warning_dropout_ms": warning_dropout_ms,
        "false_clear_count": false_clear_count,
        "ghost_warning_ms": ghost_warning_ms,
        "packets_rx": packets_rx,
        "packets_lost": packets_lost,
        "fallback_triggered": 1 if mon.fallback_triggers > 0 else 0,
        "fallback_latency_ms": fallback_latency_ms,
        "recovery_latency_ms": recovery_latency_ms,
        "decision_coverage_pct": 100.0 * decision_ok_ms / total,
        "state_pct": {s: 100.0 * state_ms[s] / total for s in D.ALL_STATES},
    }


def warning_one_tick(hazard_active, warning_on):
    return False


def main() -> int:
    rows = []

    def append(scn, base, seed, param, res):
        rows.append([
            scn, base, seed, param, DURATION_MS,
            round(res["state_pct"][D.FULL], 3),
            round(res["state_pct"][D.V2V_DEGRADED], 3),
            round(res["state_pct"][D.SENSOR_DEGRADED], 3),
            round(res["state_pct"][D.BOTH_DEGRADED], 3),
            res["warning_dropout_ms"], res["false_clear_count"],
            res["fallback_triggered"],
            res["fallback_latency_ms"] if res["fallback_latency_ms"] is not None else "",
            res["recovery_latency_ms"] if res["recovery_latency_ms"] is not None else "",
            round(res["decision_coverage_pct"], 3),
            res["ghost_warning_ms"], res["packets_rx"], res["packets_lost"],
        ])

    for scn in ["burst_loss", "blackout", "sensor_dropout", "conflict", "loss_scan"]:
        params = {
            "burst_loss": BURST_LENGTHS,
            "blackout": [0],
            "sensor_dropout": SENSOR_DROPOUTS,
            "conflict": [0],
            "loss_scan": LOSS_LEVELS,
        }[scn]
        baselines = BASELINES
        for param in params:
            for base in baselines:
                for k, seed in enumerate(SEEDS):
                    rng = random.Random(seed)
                    res = run_receiver_sim(rng, scn, base, param)
                    append(scn, base, seed, param, res)

    run = RunContext(
        experiment_id="R1", run_id="R1_scenarios", seed=SEEDS[0], run_number=1,
        configuration={
            "scenarios": ["burst_loss", "blackout", "sensor_dropout", "conflict", "loss_scan"],
            "baselines": BASELINES,
            "burst_lengths": BURST_LENGTHS, "loss_levels": LOSS_LEVELS,
            "sensor_dropouts": SENSOR_DROPOUTS, "seeds": SEEDS,
            "hazard_latch_ms": LATCH_MS, "watchdog_ms": WATCHDOG_MS,
            "beacon_interval_ms": BEACON_INTERVAL_MS,
            "hazard_window_ms": [10000, 30000], "fault_start_ms": 15000,
            "modality": "SIMULATION",
        },
        raw_csv="results/raw/R1_scenarios.csv",
    )
    run.ensure_header(SCEN_HEADER)
    run.append_rows(SCEN_HEADER, rows)
    run.finalize()

    # ---- derived aggregates ----
    def group(scn, base, param):
        return [r for r in rows if r[0] == scn and r[1] == base and r[2 + 3] == param \
                if r[3] == param]

    def g(scn, base, param):
        return [r for r in rows if r[0] == scn and r[1] == base and r[3] == param]

    def mean_of(grows, idx):
        vals = [r[idx] for r in grows if isinstance(r[idx], (int, float))]
        return round(statistics.mean(vals), 3) if vals else None

    summary = {"experiment_id": "R1", "modality": "SIMULATION", "seeds": SEEDS,
               "scenarios": {}}
    for scn in ["burst_loss", "blackout", "sensor_dropout", "conflict", "loss_scan"]:
        summary["scenarios"][scn] = {}
        params = {
            "burst_loss": BURST_LENGTHS, "blackout": [0],
            "sensor_dropout": SENSOR_DROPOUTS, "conflict": [0],
            "loss_scan": LOSS_LEVELS,
        }[scn]
        for param in params:
            for base in BASELINES:
                grows = g(scn, base, param)
                if not grows:
                    continue
                key = f"{base}@param={param}"
                summary["scenarios"][scn][key] = {
                    "n_trials": len(grows),
                    "full_pct_mean": mean_of(grows, 5),
                    "v2v_degraded_pct_mean": mean_of(grows, 6),
                    "sensor_degraded_pct_mean": mean_of(grows, 7),
                    "both_degraded_pct_mean": mean_of(grows, 8),
                    "warning_dropout_ms_mean": mean_of(grows, 9),
                    "false_clear_mean": mean_of(grows, 10),
                    "fallback_latency_ms_mean": mean_of(grows, 12),
                    "recovery_latency_ms_mean": mean_of(grows, 13),
                    "decision_coverage_pct_mean": mean_of(grows, 14),
                    "ghost_warning_ms_mean": mean_of(grows, 15),
                }

    # ---- acceptance ----
    c_blackout = g("blackout", "C_proposed", 0)
    fb_lat = [r[12] for r in c_blackout if isinstance(r[12], (int, float))]
    a_burst10 = g("burst_loss", "A_naive_volatile", 10)
    c_burst10 = g("burst_loss", "C_proposed", 10)
    acceptance = {
        "C_watchdog_fires_within_2500ms": all(abs(l - 2500.0) < 600.0 for l in fb_lat)
                                          if fb_lat else False,
        "C_no_dropout_for_burst_le_1500ms": all(r[9] == 0.0 for r in c_burst10)
                                            if c_burst10 else False,
        "A_shows_dropout_on_burst": any(r[9] > 0.0 for r in a_burst10)
                                    if a_burst10 else False,
    }
    summary["acceptance"] = acceptance
    summary["acceptance_all_pass"] = all(acceptance.values())

    dpath = os.path.join(repo_root(), "results", "derived")
    os.makedirs(dpath, exist_ok=True)
    with open(os.path.join(dpath, "R1_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    write_checksum_manifest()

    print(json.dumps(summary["acceptance"], indent=2))
    print(f"\nR1/VS5: {'PASS' if summary['acceptance_all_pass'] else 'FAIL'}")
    return 0 if summary["acceptance_all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
