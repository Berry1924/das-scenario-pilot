#!/usr/bin/env python3
"""C1 — Communication density & routine load adaptation.

Modality: SIMULATION (research EXPERIMENT_SPEC.md section 2.1; seeds 1001-1010).

Density tiers: {2, 5, 10, 20, 30, 35, 50} nodes in a 100 m zone (union of the
dual-track grids; the research agent's {5,10,20,35,50} subset is a filter on
the raw CSV). Policies: fixed 10 Hz vs adaptive (2-20 Hz) + emergency
isolation. Emergency events: Poisson arrivals (lambda = 0.05 /s), 300 s trials.

DEVIATION from spec (logged in CHANGES.md + metadata): per-packet rows are
logged for seed 1001 only; all other runs log per-run aggregate rows. CBR is
an airtime-occupancy approximation of the simplified CSMA model.

Usage:
  python3 experiments/sim_c1_density_adaptation.py
"""

import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl.channel import ChannelConfig
from daas_impl import packet as P
from daas_impl.simio import RunContext, repo_root, write_checksum_manifest
from daas_impl.world import SimulationWorld, WorldConfig, percentile

AGG_HEADER = ["run_id", "seed", "density_tier", "policy", "n_nodes",
              "duration_s", "pdr_percent", "cbr_percent",
              "rtt_mean_ms", "rtt_p95_ms", "normal_msg_per_s",
              "emergency_pdr_percent", "emergency_p95_rtt_ms",
              "emergency_preempt_p95_ms", "bytes_per_s", "packets_per_min"]
EVENT_HEADER = ["timestamp_ms", "run_id", "seed", "density_tier", "policy",
                "node_id", "packet_id", "priority", "tx_time_ms",
                "rx_time_ms", "latency_ms", "emergency_flag"]

DENSITY_TIERS = [2, 5, 10, 20, 30, 35, 50]
SEEDS = list(range(1001, 1011))
DURATION_S = 300.0
LOSS_PROB = 0.02

POLICIES = [("fixed", False), ("adaptive", True)]


def airtime_ms() -> float:
    return (P.V2V_PACKET_SIZE * 8.0) / (1.0 * 1000.0)


def main() -> int:
    agg_rows: list = []
    event_rows: list = []
    by_key: dict = {}

    agg_run = RunContext(
        experiment_id="C1", run_id="C1_density_aggregates", seed=min(SEEDS),
        run_number=1,
        configuration={
            "density_tiers": DENSITY_TIERS, "seeds": SEEDS,
            "duration_s": DURATION_S, "loss_prob": LOSS_PROB, "dt_ms": 10.0,
            "packet_bytes": P.V2V_PACKET_SIZE, "phy_rate_mbps": 1.0,
            "emergency_lambda": 0.05, "emergency_duration_ms": 2000.0,
            "policies": [p[0] for p in POLICIES],
            "event_log_policy": "seed 1001 only (per-packet); others aggregate rows",
            "cbr_definition": "airtime-occupancy approximation of simplified CSMA",
            "modality": "SIMULATION",
        },
        raw_csv="results/raw/C1_density_aggregates.csv",
    )
    agg_run.ensure_header(AGG_HEADER)

    ev_run = RunContext(
        experiment_id="C1", run_id="C1_events_seed1001", seed=min(SEEDS),
        run_number=1, configuration=agg_run.configuration,
        raw_csv="results/raw/C1_events_seed1001.csv",
    )

    for tier in DENSITY_TIERS:
        for policy, isolation in POLICIES:
            for i, seed in enumerate(SEEDS):
                rng = random.Random(seed)
                wcfg = WorldConfig(
                    duration_s=DURATION_S, dt_ms=10.0, n_nodes=tier,
                    road_length_m=100.0, comm_range_m=100.0,
                    policy=policy, emergency_isolation=isolation,
                    emergency_enabled=True, emergency_lambda=0.05,
                    emergency_duration_ms=2000.0,
                )
                ccfg = ChannelConfig(loss_prob=LOSS_PROB)
                world = SimulationWorld(wcfg, ccfg, rng)
                elog = event_rows if (seed == min(SEEDS)) else None
                m = world.run(event_log=elog)

                dur_ms = DURATION_S * 1000.0
                cbr = min(100.0, 100.0 * (m.frames_offered + m.acks_generated)
                          * airtime_ms() / dur_ms)
                row = [
                    f"C1_N{tier}_{policy}_seed{seed}", seed, tier, policy, tier,
                    DURATION_S, round(m.pdr_pct(), 4), round(cbr, 4),
                    round(statistics.mean(m.rtt_samples_ms), 3) if m.rtt_samples_ms else "",
                    round(percentile(m.rtt_samples_ms, 95), 3) if m.rtt_samples_ms else "",
                    round(m.frames_offered / tier / DURATION_S, 4),
                    round(m.emergency_pdr_pct(), 4),
                    round(percentile(m.emergency_rtt_samples_ms, 95), 3)
                    if m.emergency_rtt_samples_ms else "",
                    round(percentile(m.emergency_first_airtime_ms, 95), 3)
                    if m.emergency_first_airtime_ms else "",
                    round(m.bytes_tx / DURATION_S, 2),
                    round(m.frames_offered * 60.0 / DURATION_S, 2),
                ]
                agg_rows.append(row)
                agg_run.append_rows(AGG_HEADER, [row])
                by_key.setdefault((tier, policy), []).append(m)
            print(f"[C1] tier={tier} policy={policy}: 10 seeds done")

    if event_rows:
        ev_run.ensure_header(EVENT_HEADER)
        ev_run.append_rows(EVENT_HEADER, [
            [r[0], f"C1_seed1001", 1001, "", "", r[1], r[2], r[3],
             r[0], round(r[0] + float(r[4]), 3), float(r[4]), r[6]]
            for r in event_rows
        ])
        ev_run.finalize()
    agg_run.finalize()

    # ---- derived summary ----
    def stats(ms_list, fn):
        vals = [fn(m) for m in ms_list]
        vals = [v for v in vals if v is not None]
        if not vals:
            return {"mean": None, "std": None, "median": None, "p95": None, "n": 0}
        return {
            "mean": round(statistics.mean(vals), 4),
            "std": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
            "median": round(statistics.median(vals), 4),
            "p95": round(percentile(vals, 95), 4),
            "n": len(vals),
        }

    summary = {"experiment_id": "C1", "modality": "SIMULATION",
               "seeds": SEEDS, "tiers": {}, "paired_comparison": {}}
    for (tier, policy), ms_list in sorted(by_key.items()):
        key = f"N{tier}_{policy}"
        summary["tiers"][key] = {
            "pdr_pct": stats(ms_list, lambda m: m.pdr_pct()),
            "rtt_mean_ms": stats(ms_list, lambda m: statistics.mean(m.rtt_samples_ms)
                                 if m.rtt_samples_ms else None),
            "rtt_p95_ms": stats(ms_list, lambda m: percentile(m.rtt_samples_ms, 95)
                                if m.rtt_samples_ms else None),
            "normal_msg_per_s": stats(ms_list, lambda m: m.frames_offered / tier / DURATION_S),
            "emergency_pdr_pct": stats(ms_list, lambda m: m.emergency_pdr_pct()),
            "emergency_p95_rtt_ms": stats(ms_list, lambda m: percentile(m.emergency_rtt_samples_ms, 95)
                                          if m.emergency_rtt_samples_ms else None),
            "packets_per_min": stats(ms_list, lambda m: m.frames_offered * 60.0 / DURATION_S),
        }

    # paired B-vs-C comparison per tier (same seeds)
    for tier in DENSITY_TIERS:
        b = by_key.get((tier, "fixed"))
        c = by_key.get((tier, "adaptive"))
        if not b or not c:
            continue
        b_load = statistics.mean([m.frames_offered for m in b])
        c_load = statistics.mean([m.frames_offered for m in c])
        summary["paired_comparison"][f"N{tier}"] = {
            "fixed_packets_mean": round(b_load, 1),
            "adaptive_packets_mean": round(c_load, 1),
            "load_reduction_pct": round(100.0 * (b_load - c_load) / b_load, 3)
                                  if b_load else 0.0,
        }

    dpath = os.path.join(repo_root(), "results", "derived")
    os.makedirs(dpath, exist_ok=True)
    with open(os.path.join(dpath, "C1_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    write_checksum_manifest()

    for tier in DENSITY_TIERS:
        pc = summary["paired_comparison"].get(f"N{tier}", {})
        print(f"[C1] N={tier}: load {pc.get('fixed_packets_mean')} -> "
              f"{pc.get('adaptive_packets_mean')} packets "
              f"({pc.get('load_reduction_pct')}% reduction)")
    print("C1: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
