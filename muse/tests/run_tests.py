#!/usr/bin/env python3
"""ScenarioPilot test suite runner (stdlib unittest — no pytest needed).

Usage:
  python3 muse/tests/run_tests.py            # full muse suite
  python3 muse/tests/run_tests.py scenario   # filter by module keyword
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

if __name__ == "__main__":
    loader = unittest.defaultTestLoader
    suite = loader.discover(HERE, pattern="test_*.py",
                            top_level_dir=HERE)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    ok = result.wasSuccessful()
    n_fail = len(result.failures) + len(result.errors)
    print(f"\nmuse tests: {'PASS' if ok else 'FAIL'} "
          f"({result.testsRun} run, {n_fail} failed/errored, "
          f"{len(result.skipped)} skipped)")
    sys.exit(0 if ok else 1)
