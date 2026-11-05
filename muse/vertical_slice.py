#!/usr/bin/env python3
"""ScenarioPilot vertical slice CLI.

Validates one scenario JSON locally (strict schema; rejects invalid
parameters before anything runs), optionally requests one advisory review
from the Meta Model API (Muse Spark 1.3, credentials via environment
variables), then runs the EXISTING daas_impl world for the two implemented
arms (baseline fixed-rate vs DAAS-V2V adaptive+isolation) under identical
conditions and writes evidence + a comparison report.

Usage:
  python3 -m muse.vertical_slice muse/scenarios/vertical_slice_base.json
  python3 -m muse.vertical_slice <scenario.json> --no-spark
  python3 -m muse.vertical_slice <scenario.json> --sandbox

--sandbox runs with a scratch writer (no writes under results/) and prints
paths under the temp dir — useful for dry-runs and CI.
"""

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from muse.adapter import run_scenario_arms
from muse.reporting import write_report
from muse.scenario import ScenarioError, load_scenario
from muse.spark_adapter import SparkReview, review_scenario


class SandboxContext:
    """RunContext-shaped writer confined to a scratch directory."""

    def __init__(self, root: str, experiment_id: str, run_id: str, seed: int,
                 configuration: dict, raw_csv: str):
        self.root = root
        self.experiment_id = experiment_id
        self.run_id = run_id
        self.seed = seed
        self.configuration = configuration
        self.relpath = raw_csv  # e.g. results/raw/MUSE_*.csv
        self._file_initialized = False
        self.row_count = 0
        self.raw_csv_relpath = raw_csv
        self.metadata_json_relpath = os.path.join(
            "results", "metadata", f"{run_id}.metadata.json")

    # -- RunContext-compatible surface -------------------------------------
    def _abs(self, relpath: str) -> str:
        path = os.path.join(self.root, relpath)
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        return path

    def ensure_header(self, header):
        if not self._file_initialized:
            with open(self._abs(self.relpath), "w", newline="") as f:
                f.write(",".join(header) + "\n")
            self._file_initialized = True

    def append_rows(self, header, rows):
        if not rows:
            return
        self.ensure_header(header)
        with open(self._abs(self.relpath), "a", newline="") as f:
            for r in rows:
                f.write(
                    ",".join(str(x).replace(",", ";") for x in r) + "\n")
                self.row_count += 1

    def finalize(self, status="COMPLETE", notes=""):
        meta = {"experiment_id": self.experiment_id, "run_id": self.run_id,
                "seed": self.seed, "status": status, "notes": notes,
                "row_count": self.row_count,
                "configuration": self.configuration}
        with open(self._abs(self.metadata_json_relpath), "w") as f:
            json.dump(meta, f, indent=2, sort_keys=True)
        return None


def sandbox_factory(root_dir):
    def factory(experiment_id, run_id, seed, configuration, raw_csv):
        return SandboxContext(root_dir, experiment_id, run_id, seed,
                              configuration, raw_csv)
    return factory


def main() -> int:
    ap = argparse.ArgumentParser(description="MUSE vertical slice")
    ap.add_argument("scenario", help="path to scenario JSON")
    ap.add_argument("--no-spark", action="store_true",
                    help="skip model-API review entirely")
    ap.add_argument("--sandbox", action="store_true",
                    help="use a scratch dir instead of results/")
    args = ap.parse_args()

    try:
        spec = load_scenario(args.scenario)
    except (ScenarioError, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[SCENARIO-REJECTED] {e}")
        return 2

    print(f"[SCENARIO-OK] {spec.name} seed={spec.seed} "
          f"n={spec.num_vehicles} dur={spec.duration_s}s")

    if args.no_spark:
        review = SparkReview(status="DISABLED_NO_URL", model="muse-spark-1.3",
                             error="disabled by --no-spark flag")
        print("[SPARK] disabled by flag — advisory review skipped")
    else:
        review = review_scenario(spec)
        status = review.status
        print(f"[SPARK] model={review.model} status={status} "
              f"verdict={review.verdict or '-'}")
        if status == "REJECTED_BY_ENV":
            print("[SPARK] set MUSE_MODEL_API_URL and MUSE_MODEL_API_KEY to "
                  "enable review (advisory only)")

    sandbox_root = None
    if args.sandbox:
        sandbox_root = tempfile.mkdtemp(prefix="muse_sandbox_")
        factory = sandbox_factory(sandbox_root)
    else:
        factory = None

    results = run_scenario_arms(spec, review, ctx_factory=factory)

    for arm_name in ("baseline", "daas_v2v"):
        r = results["arms"][arm_name]
        mt = r["metrics"]
        print(f"[ARM {arm_name:9s}] policy={r['policy']:8s} "
              f"pdr={mt['pdr_percent']}% rtt_p95={mt['rtt_p95_ms']}ms "
              f"emg_pdr={mt['emergency_pdr_percent']}%")

    if args.sandbox:
        md, js = write_report(results, reports_dir=sandbox_root)
        print(f"[SANDBOX] artifacts under {sandbox_root}")
    else:
        md, js = write_report(results)
        from daas_impl.simio import write_checksum_manifest
        mpath = write_checksum_manifest()
        print(f"[CHECKSUMS] {mpath}")
    print(f"[REPORT] {md}")
    print(f"[REPORT] {js}")

    # Sanity gate: both arms must have completed and logged evidence.
    ok = all(results["arms"][a]["status"] == "COMPLETE"
             for a in ("baseline", "daas_v2v"))
    print("MUSE vertical slice: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
