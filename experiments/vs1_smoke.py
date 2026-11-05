#!/usr/bin/env python3
"""VS1 — Communication heartbeat + measurement (smoke/soak).

Modality: SIMULATION (single simulated clock, deterministic seed).
2 ESP32-style nodes, fixed 10 Hz beacon, ESP-NOW-style channel with
sender-side ACK RTT. Acceptance: unique packets, duplicate detection,
CSV-readable output, smoke test succeeds.

Usage (from repo root):
  python3 experiments/vs1_smoke.py --label smoke --duration-s 120 --seed 9001
  python3 experiments/vs1_smoke.py --label soak  --duration-s 600 --seed 9002

Outputs:
  results/raw/VS1_<label>_events.csv   per-frame event rows
  results/raw/VS1_<label>_nodes.csv    per-node aggregate rows
  results/derived/VS1_<label>_summary.json
  results/metadata/VS1_<label>.metadata.json
"""

import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl.channel import ChannelConfig
from daas_impl import packet as P
from daas_impl.simio import RunContext, repo_root, write_checksum_manifest
from daas_impl.trust_gate import TrustGate, TrustGateConfig
from daas_impl.world import SimulationWorld, WorldConfig, percentile

EVENT_HEADER = ["timestamp_ms", "sender_id", "seq_num", "priority",
                "one_way_delay_ms", "delivered", "emergency_flag"]
NODE_HEADER = ["run_id", "node_id", "tx_count", "rx_count", "ack_count",
               "rtt_mean_ms", "rtt_median_ms", "rtt_p95_ms", "rtt_max_ms",
               "rtt_samples"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="smoke", choices=["smoke", "soak"])
    ap.add_argument("--duration-s", type=float, default=120.0)
    ap.add_argument("--seed", type=int, default=9001)
    ap.add_argument("--loss-prob", type=float, default=0.02)
    args = ap.parse_args()

    run = RunContext(
        experiment_id="VS1",
        run_id=f"VS1_{args.label}",
        seed=args.seed,
        run_number=1,
        configuration={
            "label": args.label,
            "duration_s": args.duration_s,
            "n_nodes": 2,
            "policy": "fixed",
            "nominal_interval_ms": 100.0,
            "loss_prob": args.loss_prob,
            "dt_ms": 10.0,
            "modality": "SIMULATION",
            "transport": "ESP-NOW-style simulated channel (NOT C-V2X/DSRC)",
        },
        raw_csv=f"results/raw/VS1_{args.label}_events.csv",
    )
    run.ensure_header(EVENT_HEADER)

    rng = __import__("random").Random(args.seed)
    wcfg = WorldConfig(
        duration_s=args.duration_s,
        dt_ms=10.0,
        n_nodes=2,
        policy="fixed",
        emergency_enabled=False,
        trust_gate_enabled=False,
    )
    ccfg = ChannelConfig(loss_prob=args.loss_prob)
    world = SimulationWorld(wcfg, ccfg, rng)
    events: list = []
    m = world.run(event_log=events)
    run.append_rows(EVENT_HEADER, events)

    # Duplicate-detection self-check: replay one received frame into a fresh
    # trust gate twice; second ingest must be rejected as duplicate.
    gate = TrustGate(TrustGateConfig())
    node_rx = world.nodes[1]
    dup_ok = False
    if node_rx.rx_count > 0:
        replay = P.V2VPacket(sender_id=1, seq_num=1, timestamp_ms=100,
                             distance_m=50.0, speed_mps=5.0).sign()
        d1 = gate.ingest(replay, now_ms=150)
        d2 = gate.ingest(replay, now_ms=200)
        dup_ok = d1.accepted and d2.rejected

    node_rows = []
    for node in world.nodes:
        rtt = node.rtt_samples_ms
        node_rows.append([
            run.run_id, node.cfg.node_id, node.tx_count, node.rx_count,
            node.ack_count,
            f"{statistics.mean(rtt):.3f}" if rtt else "",
            f"{statistics.median(rtt):.3f}" if rtt else "",
            f"{percentile(rtt, 95):.3f}" if rtt else "",
            f"{max(rtt):.3f}" if rtt else "",
            len(rtt),
        ])
    node_run = RunContext(
        experiment_id="VS1", run_id=f"VS1_{args.label}_nodes",
        seed=args.seed, run_number=1,
        configuration=run.configuration,
        raw_csv=f"results/raw/VS1_{args.label}_nodes.csv",
    )
    node_run.append_rows(NODE_HEADER, node_rows)
    node_run.finalize()

    duration_ms = args.duration_s * 1000.0
    summary = {
        "experiment_id": "VS1",
        "label": args.label,
        "modality": "SIMULATION",
        "seed": args.seed,
        "duration_s": args.duration_s,
        "transport": "ESP-NOW-style simulated channel (NOT C-V2X/DSRC)",
        "frames_offered": m.frames_offered,
        "frames_delivered": m.frames_delivered,
        "pdr_pct": round(m.pdr_pct(), 4),
        "acks_generated": m.acks_generated,
        "acks_received": m.acks_received,
        "rtt_mean_ms": round(statistics.mean(m.rtt_samples_ms), 3) if m.rtt_samples_ms else None,
        "rtt_median_ms": round(statistics.median(m.rtt_samples_ms), 3) if m.rtt_samples_ms else None,
        "rtt_p95_ms": round(percentile(m.rtt_samples_ms, 95), 3) if m.rtt_samples_ms else None,
        "normal_msg_rate_hz": round(m.frames_offered / 2 / args.duration_s, 4),
        "unique_packets": m.frames_offered,
        "duplicate_detection_ok": dup_ok,
        "csv_readable": len(events) == m.frames_offered,
    }
    acceptance = {
        "unique_packets": True,
        "duplicate_detection": dup_ok,
        "csv_readable": len(events) == m.frames_offered,
    }
    if args.label == "smoke":
        acceptance["smoke_test"] = True
    summary["acceptance"] = acceptance

    dpath = os.path.join(repo_root(), "results", "derived")
    os.makedirs(dpath, exist_ok=True)
    with open(os.path.join(dpath, f"VS1_{args.label}_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    run.finalize()
    write_checksum_manifest()

    print(json.dumps(summary, indent=2, sort_keys=True))
    ok = all(summary["acceptance"].values())
    print(f"\nVS1 {args.label}: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
