#!/usr/bin/env python3
"""Live Muse Spark smoke test — run locally AFTER configuring the key.

Reads credentials from the environment ONLY (MUSE_MODEL_API_URL,
MUSE_MODEL_API_KEY, optional MUSE_MODEL_NAME / MUSE_MODEL_TIMEOUT_S).
The key's VALUE is never printed, logged, or written anywhere — presence
is checked, not shown.

Steps (both bounded):
  1. one small live review request;
  2. one bounded end-to-end scenario run in SANDBOX mode (scratch dir,
     nothing under results/), executed twice — once with the live review
     attached and once offline — asserting the metrics are identical,
     which demonstrates the model output does not control any
     numerical measurement.

Usage (from your own shell, after exporting the env vars):
  python3 muse/live_smoke.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from muse.adapter import run_scenario_arms
from muse.reporting import write_report
from muse.scenario import load_scenario
from muse.spark_adapter import SparkReview, review_scenario


def main() -> int:
    url = os.environ.get("MUSE_MODEL_API_URL", "").strip()
    key = os.environ.get("MUSE_MODEL_API_KEY", "").strip()
    model = os.environ.get("MUSE_MODEL_NAME", "").strip() or "muse-spark-1.3"
    print(f"[env] MUSE_MODEL_API_URL: {'SET' if url else 'UNSET'}")
    print(f"[env] MUSE_MODEL_API_KEY: {'SET (value hidden)' if key else 'UNSET'}")
    print(f"[env] MUSE_MODEL_NAME: {model}")
    if not (url and key):
        print("[SMOKE] NOT RUN — set MUSE_MODEL_API_URL and MUSE_MODEL_API_KEY "
              "in your shell environment first. Never paste the secret here.")
        return 2

    spec = load_scenario(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "muse", "scenarios", "vertical_slice_base.json"))

    print("[SMOKE 1/2] one small live review request...")
    review = review_scenario(spec)  # reads env internally
    print(f"  status={review.status} verdict={review.verdict or '-'} "
          f"latency={review.latency_ms}ms")
    if review.status != "OK":
        print(f"[SMOKE] live request FAILED ({review.status}): "
              f"{review.error}")
        if review.diagnostics:
            print(f"[SMOKE] diagnostics (safe metadata): "
                  f"{json.dumps(review.diagnostics, sort_keys=True)}")
        return 1

    print("[SMOKE 2/2] bounded end-to-end scenario (sandbox), "
          "live-review vs offline metrics comparison...")
    live = run_scenario_arms(spec, review,
                             ctx_factory=_sandbox_factory())
    offline = run_scenario_arms(
        spec, SparkReview(status="DISABLED_NO_URL", model=model),
        ctx_factory=_sandbox_factory())
    for arm in ("baseline", "daas_v2v"):
        same = live["arms"][arm]["metrics"] == offline["arms"][arm]["metrics"]
        print(f"  arm={arm}: metrics identical with vs without model "
              f"review: {same}")
        if not same:
            print("[SMOKE] FAIL — model output influenced measurements")
            return 1
    write_report(live, reports_dir=tempfile.mkdtemp(prefix="muse_smoke_"))
    print("[SMOKE] PASS — live review OK; metrics proven model-independent; "
          "artifacts in sandbox only")
    return 0


def _sandbox_factory():
    from muse.vertical_slice import sandbox_factory
    return sandbox_factory(tempfile.mkdtemp(prefix="muse_smoke_run_"))


if __name__ == "__main__":
    sys.exit(main())
