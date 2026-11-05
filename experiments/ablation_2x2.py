#!/usr/bin/env python3
"""Paired 2x2 ablation: adaptive broadcasting x emergency isolation.

Task C Step 3. Uses ONLY existing code paths: SimulationWorld/WorldConfig
(the same toggles the VS1/VS2/C1 runners exercise) and the existing metric
extraction (muse.adapter.compute_metrics over WorldMetrics). No simulator or
metric logic is changed here.

Arms (identical seed + environment within each scenario):
  A_baseline      policy=fixed,    emergency_isolation=False
  B_fixed_iso     policy=fixed,    emergency_isolation=True
  C_adapt_noiso   policy=adaptive, emergency_isolation=False
  D_daas_full     policy=adaptive, emergency_isolation=True

Scenarios:
  dense     N=35, 60 s, no emergencies   -> offered-load effect of policy
  emergency N=10, 60 s, lambda=0.2/s    -> isolation effect on emergency path

Honest expectations (tested, not assumed): B ~= A (isolation can only act
where adaptive throttling exists); C reduces offered load but may suppress
the emergency rate (VS2 finding); D reduces load while preserving the
emergency path (VS2). Modality: SIMULATION. Seeds 8001-8003.
"""

import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daas_impl.channel import ChannelConfig
from daas_impl.simio import RunContext, repo_root, write_checksum_manifest
from daas_impl.world import SimulationWorld, WorldConfig, percentile

from muse.adapter import compute_metrics

ARMS = {
    "A_baseline":    {"policy": "fixed",    "emergency_isolation": False},
    "B_fixed_iso":   {"policy": "fixed",    "emergency_isolation": True},
    "C_adapt_noiso": {"policy": "adaptive", "emergency_isolation": False},
    "D_daas_full":   {"policy": "adaptive", "emergency_isolation": True},
}
SEEDS = [8001, 8002, 8003]
DURATION_S = 60.0
DT_MS = 10.0
LOSS_PROB = 0.02
SCENARIOS = {
    "dense":     {"n_nodes": 35, "emergency_intensity": 0.0,
                  "emergency_duration_ms": 2000.0},
    "emergency": {"n_nodes": 10, "emergency_intensity": 0.2,
                  "emergency_duration_ms": 2000.0},
}
EXPERIMENT_ID = "ABL2X2"


def run_one(scenario: str, arm: str, seed: int) -> dict:
    sc = SCENARIOS[scenario]
    a = ARMS[arm]
    wcfg = WorldConfig(
        duration_s=DURATION_S, dt_ms=DT_MS, n_nodes=sc["n_nodes"],
        road_length_m=100.0, comm_range_m=100.0,
        policy=a["policy"], emergency_isolation=a["emergency_isolation"],
        emergency_enabled=sc["emergency_intensity"] > 0.0,
        emergency_lambda=sc["emergency_intensity"],
        emergency_duration_ms=sc["emergency_duration_ms"],
    )
    rng = random.Random(seed)
    config_record = {
        "scenario": scenario, "arm": arm, "seed": seed,
        "world": {k: getattr(wcfg, k) for k in (
            "duration_s", "dt_ms", "n_nodes", "road_length_m", "comm_range_m",
            "policy", "emergency_isolation", "emergency_enabled",
            "emergency_lambda", "emergency_duration_ms")},
        "channel": {"loss_prob": LOSS_PROB},
        "seeds_all": SEEDS, "arms_all": list(ARMS),
        "modality": "SIMULATION",
        "metrics_source": "WorldMetrics existing implementations",
    }
    rel = f"results/raw/ABL2X2_{scenario}_{arm}_seed{seed}.csv"
    ctx = RunContext(experiment_id=EXPERIMENT_ID,
                     run_id=f"ABL2X2_{scenario}_{arm}_seed{seed}",
                     seed=seed, run_number=1, configuration=config_record,
                     raw_csv=rel)
    events = []
    m = SimulationWorld(wcfg, ChannelConfig(loss_prob=LOSS_PROB), rng).run(
        event_log=events)
    header = ["timestamp_ms", "run_id", "scenario", "arm", "sender_id",
              "packet_seq", "priority", "one_way_delay_ms", "delivered",
              "emergency_flag"]
    ctx.ensure_header(header)
    ctx.append_rows(header, [
        [r[0], ctx.run_id, scenario, arm, r[1], r[2], r[3], r[4], r[5], r[6]]
        for r in events])
    metrics = compute_metrics(m, sc["n_nodes"], DURATION_S)
    # emergency offered rate during the trial (frames/s on the emergency path)
    metrics["emergency_offered_per_s"] = round(
        m.emergency_frames_offered / DURATION_S, 4)
    ctx.finalize(status="COMPLETE", notes="Task C 2x2 ablation arm")
    return {"scenario": scenario, "arm": arm, "seed": seed, "status": "COMPLETE",
            "metrics": metrics, "raw_csv_relpath": rel,
            "metadata_json_relpath":
                f"results/metadata/{ctx.run_id}.metadata.json"}


def main() -> int:
    results = []
    for scenario in SCENARIOS:
        for arm in ARMS:
            for seed in SEEDS:
                r = run_one(scenario, arm, seed)
                results.append(r)
                print(f"[ABL2X2] {scenario:9s} {arm:13s} seed{seed} "
                      f"pdr={r['metrics']['pdr_percent']}% "
                      f"emg_pdr={r['metrics']['emergency_pdr_percent']}% "
                      f"emg_offered/s={r['metrics']['emergency_offered_per_s']} "
                      f"pps={r['metrics']['packets_per_min']}")

    summary = {"experiment_id": EXPERIMENT_ID, "modality": "SIMULATION",
               "seeds": SEEDS, "duration_s": DURATION_S, "scenarios": {}}
    for scenario in SCENARIOS:
        agg = {}
        for arm in ARMS:
            rs = [r for r in results
                  if r["scenario"] == scenario and r["arm"] == arm]
            keys = rs[0]["metrics"].keys()
            agg[arm] = {}
            for k in keys:
                # None-valued metrics (e.g. emergency stats when no
                # emergencies fire) are absent, not zero — same convention
                # as the C1 runner's stats() helper.
                vals = [r["metrics"][k] for r in rs
                        if r["metrics"][k] is not None]
                agg[arm][k] = {
                    "mean": round(statistics.mean(vals), 4),
                    "std": round(statistics.stdev(vals), 4)
                    if len(vals) > 1 else 0.0,
                    "n": len(vals),
                } if vals else {"mean": None, "std": None, "n": 0}
        summary["scenarios"][scenario] = agg

        # paired deltas vs A_baseline (same seeds)
        def dmean(arm, key):
            return round(statistics.mean(
                [r["metrics"][key] for r in results
                 if r["scenario"] == scenario and r["arm"] == arm]), 4)
        base_load = dmean("A_baseline", "packets_per_min")
        summary["scenarios"][scenario]["paired_vs_A"] = {
            arm: {"packets_per_min_delta": round(
                      dmean(arm, "packets_per_min") - base_load, 2),
                  "pdr_delta": round(
                      dmean(arm, "pdr_percent")
                      - dmean("A_baseline", "pdr_percent"), 4)}
            for arm in ARMS}

    dpath = os.path.join(repo_root(), "results", "derived")
    with open(os.path.join(dpath, "ABL2X2_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    write_checksum_manifest()

    for scenario in SCENARIOS:
        a = summary["scenarios"][scenario]["paired_vs_A"]
        print(f"[ABL2X2 {scenario}] offered-load delta vs A: " +
              ", ".join(f"{k}:{v['packets_per_min_delta']}" for k, v in a.items()))
    print("ABL2X2: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
