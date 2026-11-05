#!/usr/bin/env python3
"""Unattended experiment runner — automation contract.

- Orchestrates the full experiment suite (1-4 h scale).
- Checkpoints at least every 30 s (heartbeat thread) to
  results/logs/run_all_checkpoint.json.
- Appends raw data (never overwrites previous runs' files).
- Saves configuration, random seeds, timestamps, software/Git version.
- Recovers cleanly from Ctrl+C: terminates the current subprocess, writes
  an INTERRUPTED checkpoint, exits non-zero.
- Never silently alters settings: every job runs with the exact documented
  argv; the checkpoint records the argv for audit.

Usage (from repo root):
  python3 experiments/run_all.py                # full suite
  python3 experiments/run_all.py --only VS1,T1  # subset
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from daas_impl.simio import repo_root, git_hash, utc_now_iso, SOFTWARE_VERSION

JOBS = [
    ("unit_tests", ["python3", "tests/run_unit_tests.py"]),
    ("fw_hostcheck", ["python3", "firmware/tests/vs1_hostcheck.py"]),
    ("fw_algorithm_tests", ["python3", "firmware/tests/run_tests.py"]),
    ("VS1_smoke", ["python3", "experiments/vs1_smoke.py", "--label", "smoke",
                   "--duration-s", "120", "--seed", "9001"]),
    ("VS1_soak", ["python3", "experiments/vs1_smoke.py", "--label", "soak",
                  "--duration-s", "600", "--seed", "9002"]),
    ("VS2", ["python3", "experiments/vs2_emergency_isolation.py"]),
    ("I1", ["python3", "experiments/sim_i1_integrity.py"]),
    ("R1", ["python3", "experiments/sim_r1_fallback.py"]),
    ("T1", ["python3", "experiments/sim_t1_message_age_ttc.py"]),
    ("F1", ["python3", "experiments/sim_f1_perception_fusion.py"]),
    ("C1", ["python3", "experiments/sim_c1_density_adaptation.py"]),
    ("analyze", ["python3", "scripts/analyze_experiment_results.py"]),
]

CHECKPOINT_INTERVAL_S = 30.0


class Checkpointer:
    def __init__(self):
        self.state = {
            "runner": "run_all.py",
            "software_version": SOFTWARE_VERSION,
            "git_hash": git_hash(),
            "started_utc": utc_now_iso(),
            "jobs": [j[0] for j in JOBS],
            "completed": [],
            "failed": [],
            "current_job": None,
            "current_argv": None,
            "elapsed_s": 0.0,
            "status": "RUNNING",
        }
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        start = time.time()
        while not self._stop.wait(CHECKPOINT_INTERVAL_S):
            self.state["elapsed_s"] = round(time.time() - start, 1)
            self._write()

    def _write(self):
        path = os.path.join(repo_root(), "results", "logs", "run_all_checkpoint.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.state, f, indent=2, sort_keys=True)

    def start(self):
        self._thread.start()

    def finalize(self, status: str):
        self.state["status"] = status
        self.state["finished_utc"] = utc_now_iso()
        self._write()
        self._stop.set()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated job names")
    args = ap.parse_args()

    jobs = JOBS
    if args.only:
        wanted = {w.strip() for w in args.only.split(",") if w.strip()}
        jobs = [j for j in JOBS if j[0] in wanted]

    cp = Checkpointer()
    cp.state["jobs"] = [j[0] for j in jobs]
    interrupted = {"flag": False}

    def on_sigint(signum, frame):
        interrupted["flag"] = True

    signal.signal(signal.SIGINT, on_sigint)
    signal.signal(signal.SIGTERM, on_sigint)
    cp.start()

    proc = None
    exit_code = 0
    for name, argv in jobs:
        if interrupted["flag"]:
            break
        cp.state["current_job"] = name
        cp.state["current_argv"] = argv
        cp._write()
        print(f"[run_all] START {name}: {' '.join(argv)}", flush=True)
        try:
            proc = subprocess.Popen(argv, cwd=repo_root())
            code = proc.wait()
        except KeyboardInterrupt:
            interrupted["flag"] = True
            code = -1
        if interrupted["flag"] and proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        if code != 0:
            cp.state["failed"].append(name)
            exit_code = 1
            print(f"[run_all] FAIL {name} (exit {code})", flush=True)
            if interrupted["flag"]:
                break
            # A failed job does not abort the suite; later jobs still run.
        else:
            cp.state["completed"].append(name)
            print(f"[run_all] DONE {name}", flush=True)
        cp.state["current_job"] = None
        cp._write()

    if interrupted["flag"]:
        cp.finalize("INTERRUPTED")
        print("[run_all] INTERRUPTED — checkpoint saved, raw data preserved",
              flush=True)
        return 130
    cp.finalize("COMPLETE" if exit_code == 0 else "COMPLETE_WITH_FAILURES")
    print(f"[run_all] finished: {len(cp.state['completed'])} ok, "
          f"{len(cp.state['failed'])} failed", flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
