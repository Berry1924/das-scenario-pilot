"""Unit tests for ScenarioPilot scenario validation (strict schema).

Run via: python3 muse/tests/run_tests.py   (stdlib unittest, no pytest)
"""

import copy
import unittest

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

from muse.scenario import (SCHEMA_VERSION, ScenarioError, ScenarioSpec,
                           scenario_hash, validate_scenario)


def base_scenario() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": "unittest_scenario",
        "seed": 7001,
        "num_vehicles": 10,
        "duration_s": 120.0,
        "dt_ms": 10.0,
        "emergency_intensity": 0.05,
        "emergency_duration_ms": 2000.0,
        "speed_mean_mps": 8.0,
        "speed_jitter_mps": 3.0,
        "loss_prob": 0.02,
        "comm_range_m": 100.0,
        "road_length_m": 100.0,
        "trust_gate_enabled": False,
        "description": "test",
    }


class TestValidScenario(unittest.TestCase):
    def test_valid_scenario_parses_every_field(self):
        s = validate_scenario(base_scenario())
        self.assertIsInstance(s, ScenarioSpec)
        self.assertEqual(s.name, "unittest_scenario")
        self.assertEqual(s.seed, 7001)
        self.assertEqual(s.num_vehicles, 10)
        self.assertAlmostEqual(s.duration_s, 120.0)
        self.assertEqual(s.trust_gate_enabled, False)
        self.assertEqual(s.loss_prob, 0.02)

    def test_description_is_optional(self):
        d = base_scenario()
        del d["description"]
        self.assertEqual(validate_scenario(d).description, "")

    def test_hash_is_order_insensitive_and_stable(self):
        d1 = base_scenario()
        d2 = dict(reversed(list(d1.items())))
        self.assertEqual(scenario_hash(validate_scenario(d1)),
                         scenario_hash(validate_scenario(d2)))


class TestRejections(unittest.TestCase):
    def assert_rejected(self, mutate, msg_fragment=""):
        d = base_scenario()
        mutate(d)
        with self.assertRaises(ScenarioError) as cm:
            validate_scenario(d)
        if msg_fragment:
            self.assertIn(msg_fragment, str(cm.exception))

    def test_missing_required_field_rejected(self):
        for key in ("name", "seed", "num_vehicles", "duration_s", "dt_ms",
                    "emergency_intensity", "emergency_duration_ms",
                    "speed_mean_mps", "speed_jitter_mps", "loss_prob",
                    "comm_range_m", "road_length_m", "trust_gate_enabled",
                    "schema_version"):
            with self.subTest(key=key):
                self.assert_rejected(lambda d, k=key: d.pop(k), key)

    def test_unknown_field_rejected_strict(self):
        self.assert_rejected(lambda d: d.update({"made_up": 1}), "made_up")

    def test_wrong_schema_version_rejected(self):
        self.assert_rejected(lambda d: d.update({"schema_version": "1.1"}),
                             "schema_version")

    def test_bad_name_rejected(self):
        self.assert_rejected(lambda d: d.update({"name": "1must_be_alpha"}))
        self.assert_rejected(lambda d: d.update({"name": ""}))
        self.assert_rejected(lambda d: d.update({"name": "a b"}))
        self.assert_rejected(lambda d: d.update({"name": 5}))

    def test_seed_bounds_and_types(self):
        self.assert_rejected(lambda d: d.update({"seed": -1}), "seed")
        self.assert_rejected(lambda d: d.update({"seed": 2**31}), "seed")
        self.assert_rejected(lambda d: d.update({"seed": 1.5}), "seed")
        self.assert_rejected(lambda d: d.update({"seed": True}), "seed")

    def test_numeric_bounds(self):
        bad_values = {
            "num_vehicles": (1, 51), "duration_s": (0.5, 1801.0),
            "dt_ms": (0.5, 101.0), "emergency_intensity": (-0.01, 1.01),
            "emergency_duration_ms": (50.0, 10001.0),
            "speed_mean_mps": (0.1, 31.0), "speed_jitter_mps": (-0.01, 21.0),
            "loss_prob": (-0.01, 0.91), "comm_range_m": (5.0, 501.0),
            "road_length_m": (5.0, 2001.0),
        }
        for key, (lo_bad, hi_bad) in bad_values.items():
            with self.subTest(key=key, value=lo_bad):
                self.assert_rejected(lambda d, k=key, v=lo_bad:
                                     d.update({k: v}), key)
            with self.subTest(key=key, value=hi_bad):
                self.assert_rejected(lambda d, k=key, v=hi_bad:
                                     d.update({k: v}), key)

    def test_wrong_types_rejected(self):
        self.assert_rejected(lambda d: d.update({"num_vehicles": "10"}))
        self.assert_rejected(lambda d: d.update({"trust_gate_enabled": 0}))
        self.assert_rejected(lambda d: d.update({"loss_prob": True}))

    def test_jitter_may_not_exceed_mean(self):
        self.assert_rejected(lambda d: d.update({"speed_jitter_mps": 50.0}))

    def test_nonfinite_rejected(self):
        self.assert_rejected(lambda d: d.update({"duration_s": float("nan")}))
        self.assert_rejected(lambda d: d.update({"duration_s":
                                                 float("inf")}))

    def test_non_dict_input_rejected(self):
        for bad in ([], "scenario", None, 3):
            with self.assertRaises(ScenarioError):
                validate_scenario(copy.deepcopy(bad))


if __name__ == "__main__":
    unittest.main(verbosity=2)
