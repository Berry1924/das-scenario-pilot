"""Adapter behaviour tests — sandboxed, deterministic, no network.

The sink is a scratch directory (SandboxContext from muse.vertical_slice);
nothing is written under results/. Run via: python3 muse/tests/run_tests.py
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

from muse.adapter import ARMS, EXPERIMENT_ID, run_scenario_arms
from muse.scenario import SCHEMA_VERSION, validate_scenario
from muse.spark_adapter import SparkReview
from muse.vertical_slice import sandbox_factory
from muse.tests.test_scenario import base_scenario


def small_scenario(**over):
    d = base_scenario()
    d.update({"name": "ad_test", "seed": 71, "num_vehicles": 3,
              "duration_s": 6.0, "dt_ms": 10.0})
    d.update(over)
    return validate_scenario(d)


def offline_review():
    return SparkReview(status="DISABLED_NO_URL", model=DEFAULT_MODEL_TEST,
                       error="offline unit test")


DEFAULT_MODEL_TEST = "muse-spark-1.3"


class TestAdapterBehaviour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="muse_adapter_")
        self.factory = sandbox_factory(self.tmp)

    def test_arms_use_the_implemented_policy_pair(self):
        self.assertEqual(ARMS["baseline"],
                         {"policy": "fixed", "emergency_isolation": False})
        self.assertEqual(ARMS["daas_v2v"],
                         {"policy": "adaptive", "emergency_isolation": True})
        self.assertEqual(EXPERIMENT_ID, "MUSE")

    def test_run_produces_complete_evidence_in_sandbox(self):
        spec = small_scenario()
        results = run_scenario_arms(spec, offline_review(),
                                    ctx_factory=self.factory)
        for arm in ("baseline", "daas_v2v"):
            r = results["arms"][arm]
            self.assertEqual(r["status"], "COMPLETE")
            self.assertGreater(r["metrics"]["frames_offered"], 0)
            events = os.path.join(self.tmp, r["raw_csv_relpath"])
            meta = os.path.join(self.tmp, r["metadata_json_relpath"])
            self.assertTrue(os.path.isfile(events), events)
            self.assertTrue(os.path.isfile(meta), meta)
            with open(meta) as f:
                m = json.load(f)
            self.assertEqual(m["status"], "COMPLETE")
            self.assertEqual(m["configuration"]["scenario_hash"],
                             results["scenario_hash"])
            self.assertIn("spark_review", m["configuration"])
            self.assertEqual(m["configuration"]["modality"], "SIMULATION")

    def test_event_rows_match_offered_frames(self):
        spec = small_scenario()
        results = run_scenario_arms(spec, offline_review(),
                                    ctx_factory=self.factory)
        for arm in ("baseline", "daas_v2v"):
            r = results["arms"][arm]
            self.assertEqual(r["events_logged"],
                             r["metrics"]["frames_offered"])

    def test_same_seed_is_deterministic_per_arm(self):
        spec = small_scenario()
        first = run_scenario_arms(spec, offline_review(),
                                  ctx_factory=self.factory)
        self.tmp2 = tempfile.mkdtemp(prefix="muse_adapter_rerun_")
        second = run_scenario_arms(spec, offline_review(),
                                   ctx_factory=sandbox_factory(self.tmp2))
        for arm in ("baseline", "daas_v2v"):
            self.assertEqual(first["arms"][arm]["metrics"],
                             second["arms"][arm]["metrics"],
                             f"arm {arm} not bit-identical across reruns")

    def test_spark_review_cannot_change_metrics(self):
        # Same scenario, two different (mocked) review outcomes: the run's
        # numbers must be identical — metrics are never model-derived.
        spec = small_scenario()
        ok = SparkReview(status="OK", model=DEFAULT_MODEL_TEST,
                         verdict="concern", summary="says something",
                         content_sha256="ab" * 32, latency_ms=7)
        r1 = run_scenario_arms(spec, offline_review(),
                               ctx_factory=self.factory)
        r2 = run_scenario_arms(spec, ok,
                               ctx_factory=sandbox_factory(
                                   tempfile.mkdtemp(prefix="muse_sparkx_")))
        for arm in ("baseline", "daas_v2v"):
            self.assertEqual(r1["arms"][arm]["metrics"],
                             r2["arms"][arm]["metrics"])

    def test_invalid_arm_name_is_rejected(self):
        from muse.adapter import run_arm
        spec = small_scenario()
        with self.assertRaises(ValueError):
            run_arm(spec, "ghost", offline_review(),
                    ctx_factory=self.factory)
        # Only the two implemented arms exist; nothing imaginary is runnable.


if __name__ == "__main__":
    unittest.main(verbosity=2)
