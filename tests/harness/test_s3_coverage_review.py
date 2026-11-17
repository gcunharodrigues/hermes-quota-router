"""Coverage admission requires executable I-level regression entry points, not scenario labels alone."""
import importlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))
sys.path.insert(0, str(ROOT / 'tests/unit'))


class CoverageReviewTests(unittest.TestCase):
    def test_process_matrix_includes_restore_and_post_crash_edits(self):
        suite = importlib.import_module('test_s3_processes').ProcessTests
        for name in ('test_apply_and_restore_crashes_check_full_projection_and_state',
                     'test_post_crash_prior_and_third_edits_are_preserved'):
            self.assertTrue(callable(getattr(suite, name, None)), name)

    def test_management_matrix_includes_consumer_toggles_and_persisted_fallbacks(self):
        suite = importlib.import_module('test_s3_scenarios').ScenarioTests
        for name in ('test_management_consumer_toggles_restore_independently_and_reenroll',
                     'test_native_option_fallback_edits_survive_apply_and_off'):
            self.assertTrue(callable(getattr(suite, name, None)), name)
