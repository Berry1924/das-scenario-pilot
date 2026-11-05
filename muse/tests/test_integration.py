"""Integration test — full slice path with a deterministic local scenario.

Validated scenario -> offline (no-key) model review -> both arms through the
existing world in a sandbox -> evidence files -> comparison report, whose
referenced artifacts must all exist. No live API key required, no writes
under results/.
Run via: python3 muse/tests/run_tests.py
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

from muse.reporting import write_report
from muse.scenario import SCHEMA_VERSION, load_scenario, validate_scenario
from muse.adapter import run_scenario_arms
from muse.spark_adapter import SparkReview, review_scenario
from muse.vertical_slice import sandbox_factory
from muse.tests.test_scenario import base_scenario


class TestVerticalSliceIntegration(unittest.TestCase):
    def test_full_slice_end_to_end_offline(self):
        sandbox = tempfile.mkdtemp(prefix="muse_integration_")
        # Deterministic local scenario: derived from the base template but
        # shrunk for CI speed; every field validated by the strict schema.
        d = base_scenario()
        d.update({"name": "integration_slice", "seed": 7101,
                  "num_vehicles": 4, "duration_s": 20.0})
        spec = validate_scenario(d)

        # No MUSE_MODEL_* environment variables are set in tests: the review
        # must report offline mode without touching the network.
        review = review_scenario(spec, env={})
        self.assertEqual(review.status, "DISABLED_NO_URL")

        results = run_scenario_arms(spec, review,
                                    ctx_factory=sandbox_factory(sandbox))
        md_path, json_path = write_report(
            results, reports_dir=os.path.join(sandbox, "reports"))

        # Evidence files exist and are non-empty.
        for arm in ("baseline", "daas_v2v"):
            p = os.path.join(sandbox, results["arms"][arm]["raw_csv_relpath"])
            self.assertTrue(os.path.isfile(p) and
                            os.path.getsize(p) > 0, p)
        self.assertTrue(os.path.isfile(md_path))
        self.assertTrue(os.path.isfile(json_path))

        # Report records the honest provenance chain.
        with open(md_path, encoding="utf-8") as f:
            md = f.read()
        self.assertIn("SIMULATION", md)
        self.assertIn("baseline", md)
        self.assertIn("daas_v2v", md)
        self.assertIn("advisory only", md)
        self.assertIn(str(spec.seed), md)
        for arm in ("baseline", "daas_v2v"):
            self.assertIn(results["arms"][arm]["raw_csv_relpath"], md)

        with open(json_path, encoding="utf-8") as f:
            rep = json.load(f)
        self.assertEqual(rep["spark_review"]["status"], "DISABLED_NO_URL")
        self.assertEqual(set(rep["arms"].keys()), {"baseline", "daas_v2v"})
        self.assertIn("PDR (%)", rep["paired_deltas"])
        self.assertEqual(rep["modality"], "SIMULATION")
        self.assertEqual(
            rep["scenario"]["schema_version"], SCHEMA_VERSION)

    def test_bundled_template_is_valid_and_deterministic(self):
        tpl = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "scenarios",
            "vertical_slice_base.json")
        spec = load_scenario(tpl)
        self.assertEqual(spec.name, "vertical_slice_base")
        self.assertEqual(spec.seed, 7001)


if __name__ == "__main__":
    unittest.main(verbosity=2)
