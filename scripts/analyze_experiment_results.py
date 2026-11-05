#!/usr/bin/env python3
"""REQ-06 — Automated statistical synthesis + SHA-256 manifest.

Ingests raw CSVs from results/raw/, computes Mean / Std / 95% CI summary
statistics, writes structured summary JSONs to results/derived/, and
generates results/raw/CHECKSUMS.sha256 guaranteeing raw data immutability.

Usage (from repo root):
  python3 scripts/analyze_experiment_results.py
"""

import csv
import json
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl.simio import repo_root, write_checksum_manifest, verify_checksum_manifest


def ci95(vals: list) -> float | None:
    """95% CI half-width via Student-t (large-n normal approximation)."""
    n = len(vals)
    if n < 2:
        return None
    # t critical values for common n; fall back to normal 1.96 for n >= 30
    t_table = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447,
               8: 2.365, 9: 2.306, 10: 2.262, 15: 2.145, 20: 2.093}
    t = t_table.get(n, 1.96 if n >= 30 else 2.093)
    se = statistics.stdev(vals) / math.sqrt(n)
    return round(t * se, 4)


def summarize_numeric_columns(rows: list[dict], exclude: set) -> dict:
    out = {}
    cols = [c for c in rows[0].keys() if c not in exclude] if rows else []
    for col in cols:
        vals = []
        for r in rows:
            v = r.get(col, "")
            if v in ("", None):
                continue
            try:
                vals.append(float(v))
            except (ValueError, TypeError):
                continue
        if not vals:
            continue
        out[col] = {
            "n": len(vals),
            "mean": round(statistics.mean(vals), 4),
            "std": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
            "median": round(statistics.median(vals), 4),
            "ci95_halfwidth": ci95(vals),
        }
    return out


def main() -> int:
    root = repo_root()
    raw_dir = os.path.join(root, "results", "raw")
    derived_dir = os.path.join(root, "results", "derived")
    os.makedirs(derived_dir, exist_ok=True)

    # exclude non-numeric / identifier columns from blanket statistics
    EXCLUDE = {"run_id", "seed", "density_tier", "node_id", "packet_id",
               "priority", "timestamp_ms", "sender_id", "seq_num",
               "packet_id", "injected_class", "trajectory_id", "config",
               "baseline", "method", "visibility_tier", "fault_param",
               "metric", "emergency_flag", "delivered", "crc_pass",
               "seq_pass", "age_pass", "bounds_pass", "gate_decision",
               "baseline_A_accepted", "baseline_B_accepted", "false_positive",
               "false_negative", "emergency_flag", "peer_fresh", "decision_ok",
               "leader_tx_priority", "deg_state"}

    report = {"generated_for": "REQ-06 statistical synthesis",
              "files": {}}
    for name in sorted(os.listdir(raw_dir)):
        if not name.endswith(".csv") or name == "CHECKSUMS.sha256":
            continue
        path = os.path.join(raw_dir, name)
        with open(path) as f:
            rows = list(csv.DictReader(f))
        stats = summarize_numeric_columns(rows, EXCLUDE)
        report["files"][name] = {"rows": len(rows), "columns_stats": stats}
        out_name = name.replace(".csv", "_summary.json")
        with open(os.path.join(derived_dir, out_name), "w") as f:
            json.dump({"source_raw": f"results/raw/{name}",
                       "rows": len(rows), "statistics": stats}, f,
                      indent=2, sort_keys=True)

    # checksum manifest + verification
    manifest = write_checksum_manifest()
    ok, bad = verify_checksum_manifest()
    report["checksum_manifest"] = {
        "path": "results/raw/CHECKSUMS.sha256",
        "files_covered": ok,
        "mismatched": bad,
        "verified": len(bad) == 0,
    }

    with open(os.path.join(derived_dir, "ALL_EXPERIMENTS_stats_summary.json"), "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    print(f"[analyze] summarized {len(report['files'])} raw CSV files")
    print(f"[analyze] checksum manifest: {ok} files verified, "
          f"{len(bad)} mismatched")
    return 0 if len(bad) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
