"""Controlled adapter: validated scenarios -> existing daas_impl world.

Two arms per scenario, using ONLY implemented behaviour:

  baseline : policy="fixed",    emergency_isolation=False
  daas_v2v : policy="adaptive", emergency_isolation=True

(the same implemented pair the VS2/C1 runners exercise). The world, channel,
nodes and metrics come from src/daas_impl unchanged. Metrics are extracted
solely through WorldMetrics' existing members and helper methods — no
recomputation, and no model/API involvement in any number.

Evidence persistence reuses RunContext (simulation contract). A writer
factory can be injected in tests to sandbox file output; the writer only
needs ensure_header/append_rows/finalize — RunContext already qualifies.
"""

import os
import random
import statistics
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "src"))

from daas_impl.channel import ChannelConfig
from daas_impl.simio import RunContext, repo_root, git_hash
from daas_impl.world import SimulationWorld, WorldConfig, percentile

from muse.scenario import ScenarioSpec, scenario_hash
from muse.spark_adapter import SparkReview

ARMS = {
    "baseline": {"policy": "fixed", "emergency_isolation": False},
    "daas_v2v": {"policy": "adaptive", "emergency_isolation": True},
}

EVENT_HEADER = ["timestamp_ms", "run_id", "arm", "sender_id", "packet_seq",
                "priority", "one_way_delay_ms", "delivered",
                "emergency_flag"]

EXPERIMENT_ID = "MUSE"


def compute_metrics(m, n_nodes: int, duration_s: float) -> dict:
    """Extract the metric set via existing WorldMetrics implementations."""
    return {
        "pdr_percent": round(m.pdr_pct(), 4),
        "rtt_mean_ms": round(statistics.mean(m.rtt_samples_ms), 3)
        if m.rtt_samples_ms else None,
        "rtt_p95_ms": round(percentile(m.rtt_samples_ms, 95), 3)
        if m.rtt_samples_ms else None,
        "normal_msg_per_s": round(m.frames_offered / n_nodes / duration_s, 4),
        "emergency_pdr_percent": round(m.emergency_pdr_pct(), 4),
        "emergency_p95_rtt_ms": round(
            percentile(m.emergency_rtt_samples_ms, 95), 3)
        if m.emergency_rtt_samples_ms else None,
        "emergency_preempt_p95_ms": round(
            percentile(m.emergency_first_airtime_ms, 95), 3)
        if m.emergency_first_airtime_ms else None,
        "bytes_per_s": round(m.bytes_tx / duration_s, 2),
        "packets_per_min": round(m.frames_offered * 60.0 / duration_s, 2),
        "frames_offered": m.frames_offered,
        "frames_delivered": m.frames_delivered,
        "acks_generated": m.acks_generated,
        "acks_received": m.acks_received,
    }


def _world_config(spec: ScenarioSpec, arm: str) -> WorldConfig:
    a = ARMS[arm]
    return WorldConfig(
        duration_s=spec.duration_s,
        dt_ms=spec.dt_ms,
        n_nodes=spec.num_vehicles,
        road_length_m=spec.road_length_m,
        comm_range_m=spec.comm_range_m,
        policy=a["policy"],
        emergency_isolation=a["emergency_isolation"],
        emergency_enabled=spec.emergency_intensity > 0.0,
        emergency_lambda=spec.emergency_intensity,
        emergency_duration_ms=spec.emergency_duration_ms,
        speed_mean_mps=spec.speed_mean_mps,
        speed_jitter_mps=spec.speed_jitter_mps,
        trust_gate_enabled=spec.trust_gate_enabled,
    )


def _events_csv_relpath(spec: ScenarioSpec, arm: str) -> str:
    return (f"results/raw/MUSE_{spec.name}_{arm}"
            f"_seed{spec.seed}.csv")


def run_arm(spec: ScenarioSpec, arm: str, review: SparkReview,
            ctx_factory=None) -> dict:
    """Run one arm of a validated scenario through the existing world.

    ctx_factory(experiment_id, run_id, seed, configuration, raw_csv_relpath)
    must return an object implementing ensure_header/append_rows/finalize;
    default is the production RunContext.
    """
    if arm not in ARMS:
        raise ValueError(f"unknown arm '{arm}'")
    cfg = _world_config(spec, arm)
    ccfg = ChannelConfig(loss_prob=spec.loss_prob)
    rng = random.Random(spec.seed)

    config_record = {
        "schema_version": spec.raw.get("schema_version"),
        "scenario_name": spec.name,
        "scenario_hash": scenario_hash(spec),
        "arm": arm,
        "policy": cfg.policy,
        "emergency_isolation": cfg.emergency_isolation,
        "emergency_enabled": cfg.emergency_enabled,
        "world": {k: getattr(cfg, k) for k in (
            "duration_s", "dt_ms", "n_nodes", "road_length_m", "comm_range_m",
            "emergency_lambda", "emergency_duration_ms", "speed_mean_mps",
            "speed_jitter_mps", "trust_gate_enabled")},
        "channel": {"loss_prob": spec.loss_prob},
        "seed": spec.seed,
        "random_reseeding": "single random.Random(seed) per arm run",
        "spark_review": review.to_dict(),
        "spark_role": "advisory-only; no numeric influence",
        "metrics_source": "WorldMetrics existing implementations",
        "modality": "SIMULATION",
    }

    events_rel = _events_csv_relpath(spec, arm)
    if ctx_factory is None:
        def ctx_factory(experiment_id, run_id, seed, configuration, raw_csv):
            return RunContext(experiment_id=experiment_id, run_id=run_id,
                              seed=seed, run_number=1,
                              configuration=configuration, raw_csv=raw_csv)
    ctx = ctx_factory(EXPERIMENT_ID, f"MUSE_{spec.name}_{arm}", spec.seed,
                      config_record, events_rel)

    event_rows: list = []
    m = SimulationWorld(cfg, ccfg, rng).run(event_log=event_rows)
    ctx.ensure_header(EVENT_HEADER)
    ctx.append_rows(EVENT_HEADER, [
        [r[0], f"MUSE_{spec.name}_{arm}", arm, r[1], r[2], r[3],
         r[4], r[5], r[6]]
        for r in event_rows
    ])
    raw = m
    metrics = compute_metrics(raw, spec.num_vehicles, spec.duration_s)
    ctx.finalize(status="COMPLETE", notes="muse vertical slice arm")
    results = {
        "arm": arm,
        "policy": cfg.policy,
        "emergency_isolation": cfg.emergency_isolation,
        "seed": spec.seed,
        "events_logged": len(event_rows),
        "status": "COMPLETE",
        "metrics": metrics,
        "raw_csv_relpath": events_rel,
        "metadata_json_relpath":
            f"results/metadata/MUSE_{spec.name}_{arm}.metadata.json",
    }
    return results


def run_scenario_arms(spec: ScenarioSpec, review: SparkReview,
                      ctx_factory=None) -> dict:
    """Run both arms; same seed and env for both (identical conditions)."""
    results = {"spec": spec, "review": review,
               "scenario_hash": scenario_hash(spec), "arms": {}}
    for arm in ("baseline", "daas_v2v"):
        res = run_arm(spec, arm, review, ctx_factory=ctx_factory)
        res["configuration_sha_note"] = (
            "same seed + same environment fields as the other arm; only the "
            "implemented policy attributes (and their isolation flag) differ")
        results["arms"][arm] = res
    return results
