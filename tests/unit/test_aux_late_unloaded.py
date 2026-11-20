# Contract: decisions/aux-plan.md, AUXP-04/H9/H13/H20: OFF must also discover obligations with no initial main Engine.
"""Sibling retained-state boundaries, with separate management instances and synthetic configuration only."""
import json
from pathlib import Path
import tempfile
import unittest

import test_aux_late_retained as fixtures
from s3_fakes import qualified


class LateUnloadedAuxiliaryTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.LateRetainedAuxiliaryTests()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_off_without_initial_engine_discovers_late_state_even_at_lock_acquisition(self):
        for drift in (False, True):
            for timing in ('before_command', 'before_lock'):
                with self.subTest(drift=drift, timing=timing), tempfile.TemporaryDirectory() as root:
                    fixture = self.fixture()
                    first, ctx, backend, _ = fixture.manager(root, enabled=False)
                    baseline = backend.read()
                    self.assertIsNone(first.engine)
                    second, _, _, _ = fixture.manager(root, ctx=ctx, backend=backend)
                    # Enroll only the main consumer, leaving first without either Engine.
                    self.assertTrue(fixture.call(second, 'mode auto')['ok'])
                    self.assertIsNone(first.engine)
                    if drift:
                        first.auxiliary_compatible = lambda: {'ok': False, 'fingerprint_failure': True,
                                                            'reasons': ['agent.auxiliary_client.call_llm']}
                    with fixture.publication(timing, second, ctx):
                        result = fixture.call(first, 'mode off')
                    self.assertTrue(result['ok'], result)
                    self.assertEqual(result['mode_effective'], 'off')
                    self.assertEqual(backend.read()['model'], baseline['model'])
                    self.assertEqual(result['applied']['auxiliary']['restoration_pending'], drift)
                    if drift:
                        self.assertNotEqual(backend.read()['auxiliary'], baseline['auxiliary'])
                        first.auxiliary_compatible = qualified
                        self.assertTrue(fixture.call(first, 'mode off')['ok'])
                    self.assertEqual(backend.read(), baseline)

    def test_off_report_discovers_late_state_reloads_cached_state_and_marks_absence_without_writes(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = self.fixture()
            first, second, ctx, backend, baseline = fixture.pair(root)
            self.assertTrue(fixture.call(first, 'mode off')['ok'])
            self.assertIsNone(first.aux_engine)
            fixture.publish(second, ctx)
            retained = Path(root, 'aux-state.json').read_bytes()
            document, count = backend.read(), len(backend.writes)
            report = fixture.call(first, 'status')
            self.assertTrue(report['ok'], report)
            self.assertTrue(report['applied']['auxiliary']['restoration_pending'])
            self.assertIsNotNone(report['applied']['auxiliary']['absence'])
            self.assertEqual(backend.read(), document)
            self.assertEqual(len(backend.writes), count)
            self.assertEqual(Path(root, 'aux-state.json').read_bytes(), retained)
            self.assertTrue(fixture.call(second, 'mode off')['ok'])
            updated = fixture.call(first, 'status')
            self.assertFalse(updated['applied']['auxiliary']['restoration_pending'])
            self.assertTrue(all(not entry['active'] for entry in updated['applied']['auxiliary']['groups'].values()))
            self.assertEqual(backend.read(), baseline)

    def test_late_invalid_auxiliary_state_refuses_off_without_overwriting_configuration_or_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = self.fixture()
            first, second, ctx, backend, _ = fixture.pair(root)
            fixture.publish(second, ctx)
            path = Path(root, 'aux-state.json')
            state = json.loads(path.read_bytes())
            state['groups']['aux:compression']['baseline']['provider'] = {'present': True, 'value': 'invalid'}
            path.write_text(json.dumps(state))
            evidence, before, count = path.read_bytes(), backend.read(), len(backend.writes)
            result = fixture.call(first, 'mode off')
            self.assertFalse(result['ok'])
            self.assertEqual(ctx.settings['mode'], 'auto')
            self.assertEqual(first.mode, 'auto')
            self.assertEqual(backend.read(), before)
            self.assertEqual(len(backend.writes), count)
            self.assertEqual(path.read_bytes(), evidence)
            self.assertIsNone(first.engine._directory_fd)
            if first.aux_engine is not None:
                self.assertIsNone(first.aux_engine._directory_fd)
