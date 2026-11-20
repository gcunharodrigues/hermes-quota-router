"""Exercise the installed driver's scenario logic with the hermetic config backend."""
from pathlib import Path
import importlib.util
import unittest

import test_hqr38_fallback as support
from quota_router import readings


class ExerciseTests(unittest.TestCase):
    def test_s1_sequence(self):
        source = Path(__file__).resolve().parents[1] / 'installed' / 'd43_exercise.py'
        spec = importlib.util.spec_from_file_location('d43_exercise', source)
        assert spec and spec.loader
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        harness = support.SafetyNetLifecycleTests()
        with harness.fixture() as (manager, backend, _, snapshots):
            def collect(case):
                codex = support.codex(100 if case == 'exhausted' else 60)
                if case == 'malformed':
                    assert codex.raw is not None
                    codex.raw['rate_limit']['tertiary_window'] = {'used_tokens': 10}
                snapshots['openai_codex'] = readings._NativeFailure({'kind': 'timeout'}) if case == 'timeout' else codex
                snapshots['anthropic'] = support.claude(80 if case == 'seed' else 10)
                manager.cache.clear()

            result = driver.exercise(lambda text: harness.call(manager, text), backend.read,
                                     lambda config: config['model'], collect)
            self.assertEqual(result['confirmed_exhaustion']['provider'], 'anthropic')
