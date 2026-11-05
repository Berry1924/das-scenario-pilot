#!/usr/bin/env python3
"""Build the machine-readable evidence manifest (freeze rule 9).

Maps: experiment -> raw file -> derived file -> figure -> metric ->
configuration -> seed -> Git commit. Sources: results/metadata/*.metadata.json
(the per-run registry) plus a static experiment->artifact map.

Output: results/metadata/EVIDENCE_MANIFEST.json + EVIDENCE_MANIFEST.csv

Usage (from repo root):
  python3 scripts/build_evidence_manifest.py
"""

import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl.simio import repo_root, git_hash, utc_now_iso, SOFTWARE_VERSION

EXPERIMENT_MAP = {
    "VS1": {
        "title": "Communication heartbeat + ACK-RTT (smoke/soak)",
        "modality": "SIMULATION",
        "raw": ["results/raw/VS1_smoke_events.csv", "results/raw/VS1_smoke_nodes.csv",
                "results/raw/VS1_soak_events.csv", "results/raw/VS1_soak_nodes.csv"],
        "derived": ["results/derived/VS1_smoke_summary.json",
                    "results/derived/VS1_soak_summary.json"],
        "figures": [],
        "metrics": ["pdr_pct", "rtt_mean_ms", "rtt_p95_ms", "normal_msg_rate_hz",
                    "unique_packets", "duplicate_detection_ok"],
        "seeds": [9001, 9002],
    },
    "VS2": {
        "title": "Emergency isolation under adaptive normal traffic",
        "modality": "SIMULATION",
        "raw": ["results/raw/VS2_aggregates.csv", "results/raw/VS2_events_seed9101.csv"],
        "derived": ["results/derived/VS2_summary.json"],
        "figures": ["results/plots/VS2_isolation.png"],
        "metrics": ["emergency_pdr_pct", "emergency_rtt_p95_ms",
                    "emergency_msg_rate_hz", "emergency_preempt_p95_ms",
                    "normal_pdr_pct", "normal_msg_rate_hz"],
        "seeds": [9101, 9102, 9103, 9104, 9105],
    },
    "VS3": {
        "title": "Trust gate (served by I1 fault injection)",
        "modality": "SIMULATION",
        "raw": ["results/raw/I1_gate_decisions.csv"],
        "derived": ["results/derived/I1_summary.json"],
        "figures": [],
        "metrics": ["anomaly_rejection_rate_pct", "false_rejection_rate_pct",
                    "rejection_by_class_pct", "exec_time_us"],
        "seeds": [3001],
    },
    "VS6": {
        "title": "Full integration slice",
        "modality": "SIMULATION",
        "raw": ["results/raw/VS6_timeline.csv"],
        "derived": ["results/derived/VS6_summary.json"],
        "figures": [],
        "metrics": ["pdr_leader_frames_pct", "rtt_mean_ms", "rtt_p95_ms",
                    "watchdog_latency_ms", "recovery_latency_ms",
                    "decision_coverage_pct", "risk_reached_critical"],
        "seeds": [6001],
    },
    "C1": {
        "title": "Communication density & routine load adaptation",
        "modality": "SIMULATION",
        "raw": ["results/raw/C1_density_aggregates.csv",
                "results/raw/C1_events_seed1001.csv"],
        "derived": ["results/derived/C1_summary.json"],
        "figures": ["results/plots/C1_density.png"],
        "metrics": ["pdr_pct", "cbr_percent", "rtt_p95_ms", "normal_msg_per_s",
                    "emergency_pdr_percent", "emergency_p95_rtt_ms",
                    "packets_per_min", "load_reduction_pct"],
        "seeds": list(range(1001, 1011)),
    },
    "F1": {
        "title": "Perception degradation: local vs V2V vs fusion",
        "modality": "SIMULATION",
        "raw": ["results/raw/F1_fusion_raw.csv"],
        "derived": ["results/derived/F1_summary.json"],
        "figures": ["results/plots/F1_fusion.png"],
        "metrics": ["warning_distance_m", "lead_time_s", "false_positive_rate_pct",
                    "false_negative_rate_pct", "alarm_toggles", "valid_info_fraction"],
        "seeds": list(range(2001, 2021)),
    },
    "R1": {
        "title": "Communication & sensor failure with graceful fallback",
        "modality": "SIMULATION",
        "raw": ["results/raw/R1_scenarios.csv"],
        "derived": ["results/derived/R1_summary.json"],
        "figures": ["results/plots/R1_fallback.png"],
        "metrics": ["warning_dropout_ms", "false_clear_count",
                    "fallback_latency_ms", "recovery_latency_ms",
                    "decision_coverage_pct", "state_occupancy_pct"],
        "seeds": list(range(5001, 5006)),
    },
    "I1": {
        "title": "Message integrity: trust-gate fault injection",
        "modality": "SIMULATION",
        "raw": ["results/raw/I1_gate_decisions.csv"],
        "derived": ["results/derived/I1_summary.json"],
        "figures": [],
        "metrics": ["anomaly_rejection_rate_pct", "false_rejection_rate_pct",
                    "exec_time_us"],
        "seeds": [3001],
    },
    "T1": {
        "title": "Message age vs TTC estimation error",
        "modality": "SIMULATION",
        "raw": ["results/raw/T1_age_rmse.csv",
                "results/raw/T1_timeseries_seed4001.csv"],
        "derived": ["results/derived/T1_summary.json"],
        "figures": ["results/plots/T1_age_vs_ttc_error.png"],
        "metrics": ["ttc_rmse_s", "ttc_mae_s", "max_abs_err_s",
                    "false_clear_share", "warn_delay_ms_stale", "fit_rmse_alpha",
                    "fit_rmse_beta"],
        "seeds": list(range(4001, 4051)),
    },
}


def main() -> int:
    root = repo_root()
    meta_files = sorted(glob.glob(os.path.join(root, "results", "metadata",
                                               "*.metadata.json")))
    runs = []
    for mf in meta_files:
        with open(mf) as f:
            runs.append(json.load(f))

    manifest = {
        "generated_utc": utc_now_iso(),
        "software_version": SOFTWARE_VERSION,
        "git_hash": git_hash(),
        "modality_note": ("ALL numerical results in this manifest are "
                          "SIMULATION / SOFTWARE-LEVEL. No hardware bench or "
                          "field data is included."),
        "experiments": {},
        "runs": runs,
    }

    missing = []
    for exp_id, info in EXPERIMENT_MAP.items():
        entry = dict(info)
        entry["artifact_status"] = {}
        for kind, paths in [("raw", info["raw"]), ("derived", info["derived"]),
                            ("figures", info["figures"])]:
            for p in paths:
                exists = os.path.isfile(os.path.join(root, p))
                entry["artifact_status"][p] = "PRESENT" if exists else "MISSING"
                if not exists:
                    missing.append((exp_id, p))
        manifest["experiments"][exp_id] = entry

    out_json = os.path.join(root, "results", "metadata", "EVIDENCE_MANIFEST.json")
    with open(out_json, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    out_csv = os.path.join(root, "results", "metadata", "EVIDENCE_MANIFEST.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["experiment_id", "title", "modality", "raw_files",
                    "derived_files", "figures", "metrics", "seeds",
                    "git_hash", "software_version"])
        for exp_id, e in manifest["experiments"].items():
            w.writerow([exp_id, e["title"], e["modality"],
                        ";".join(e["raw"]), ";".join(e["derived"]),
                        ";".join(e["figures"]), ";".join(e["metrics"]),
                        ";".join(map(str, e["seeds"])),
                        manifest["git_hash"], manifest["software_version"]])

    print(f"[manifest] {len(manifest['experiments'])} experiments, "
          f"{len(runs)} run records")
    if missing:
        for exp_id, p in missing:
            print(f"[manifest] MISSING: {exp_id} -> {p}")
    print(f"[manifest] written: results/metadata/EVIDENCE_MANIFEST.json + .csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
