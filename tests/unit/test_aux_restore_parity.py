# Contract: decisions/aux-plan.md, AUXP-04/OFF; decisions/s3-plan.md, "Escopo"; AUXI3-R02.
"""OFF refusal parity: a retained auxiliary Engine must not bypass the main Auto gate (synthetic data only)."""
import json
from pathlib import Path
import tempfile
import unittest

import test_aux_lifecycle as lifecycle
from s3_fakes import qualified

RECORDS = ('state.json', 'journal.json', 'aux-state.json', 'aux-journal.json')
DRIFT = {'ok': False, 'reasons': ['agent.auxiliary_client.call_llm'], 'fingerprint_failure': True}


class AuxiliaryRestoreParityTests(unittest.TestCase):
    def fixture(self):
        fixture = lifecycle.AuxiliaryLifecycleTests('test_default_off_previews_without_creating_engine_or_writing_auxiliary')
        self.addCleanup(fixture.doCleanups)
        return fixture

    def records(self, root):
        return {name: Path(root, name).read_bytes() for name in RECORDS if Path(root, name).exists()}

    def prepare(self, fixture, root, auxiliary):
        """Leave Auto applied with no auxiliary Engine, a retained inactive one, or active auxiliary groups."""
        manager, ctx, backend, _ = fixture.manager(root, enabled=auxiliary != 'none')
        baseline = backend.read()
        self.assertTrue(fixture.call(manager, 'mode auto')['ok'])
        if auxiliary == 'retained':
            # A past auxiliary cycle followed by a complete OFF keeps aux-state.json on disk.
            self.assertTrue(fixture.call(manager, 'mode off')['ok'])
            self.assertEqual(backend.read(), baseline)
            ctx.settings['consumers.auxiliary'] = False
            self.assertTrue(fixture.call(manager, 'mode auto')['ok'])
        self.assertEqual(Path(root, 'aux-state.json').exists(), auxiliary != 'none')
        self.assertNotEqual(backend.read()['model'], baseline['model'])
        return manager, ctx, backend, baseline

    def inject(self, fixture, root, manager, ctx, backend, failure):
        """Inject one Auto gate failure and return the instance that will receive `mode off`."""
        if failure == 'latch':
            original = backend.read
            def unreadable():
                raise OSError('SYNTHETIC_PRIVATE_VALUE')
            backend.read = unreadable
            fixture.call(manager, 'apply')
            backend.read = original
            self.assertEqual(manager.auto_failure, 'native_state_or_config_unavailable')
            return manager
        manager.close()
        if failure == 'invalid_settings':
            ctx.settings['limits.week_block_pct'] = 999
        reloaded = fixture.manager(root, ctx=ctx, backend=backend)[0]
        if failure == 'read_failure':
            original = ctx.get_config
            def get_config(key, default=None):
                if key == 'limits.week_block_pct':
                    raise OSError('SYNTHETIC_PRIVATE_VALUE')
                return original(key, default)
            ctx.get_config = get_config
        elif failure == 'profile':
            reloaded.profile = lambda: 'other'
        return reloaded

    def assert_refused_without_writes(self, fixture, root, manager, ctx, backend, mode):
        document, count, records = backend.read(), len(backend.writes), self.records(root)
        result = fixture.call(manager, 'mode off')
        self.assertFalse(result['ok'], result)
        self.assertEqual(result['error'], 'Auto restoration incomplete')
        self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', json.dumps(result))
        self.assertEqual(ctx.settings['mode'], mode)
        self.assertEqual(len(backend.writes), count)
        self.assertEqual(backend.read(), document)
        self.assertEqual(self.records(root), records)

    def test_auto_gate_failures_refuse_off_with_zero_writes_for_both_engines(self):
        for failure in ('latch', 'invalid_settings', 'read_failure'):  # D-37: no profile gate
            for auxiliary in ('none', 'retained', 'active'):
                with self.subTest(failure=failure, auxiliary=auxiliary), tempfile.TemporaryDirectory() as root:
                    fixture = self.fixture()
                    manager, ctx, backend, baseline = self.prepare(fixture, root, auxiliary)
                    target = self.inject(fixture, root, manager, ctx, backend, failure)
                    self.assert_refused_without_writes(fixture, root, target, ctx, backend, 'auto')
                    # The refusal is recoverable: a reload with a valid gate restores the exact baseline.
                    target.close()
                    ctx.get_config = type(ctx).get_config.__get__(ctx)
                    ctx.settings.pop('limits.week_block_pct', None)
                    healthy = fixture.manager(root, ctx=ctx, backend=backend)[0]
                    result = fixture.call(healthy, 'mode off')
                    self.assertTrue(result['ok'], result)
                    self.assertEqual(backend.read(), baseline)

    def test_pending_auxiliary_obligation_after_main_off_still_requires_the_auto_gate(self):
        for failure in ('latch', 'invalid_settings', 'read_failure'):  # D-37: no profile gate
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as root:
                fixture = self.fixture()
                manager, ctx, backend, baseline = self.prepare(fixture, root, 'active')
                manager.auxiliary_compatible = lambda: dict(DRIFT)
                result = fixture.call(manager, 'mode off')
                self.assertTrue(result['ok'], result)
                self.assertTrue(result['applied']['auxiliary']['restoration_pending'])
                self.assertEqual(backend.read()['model'], baseline['model'])
                self.assertNotEqual(backend.read()['auxiliary'], baseline['auxiliary'])
                manager.auxiliary_compatible = qualified
                if failure == 'latch':
                    # O1: OFF status validates retained records under the lock; a transient invalid record latches until reload.
                    path = Path(root, 'aux-state.json')
                    retained = path.read_bytes()
                    path.write_text('{"schema": "SYNTHETIC_INVALID"}')
                    fixture.call(manager, 'status')
                    path.write_bytes(retained)
                    self.assertEqual(manager.auto_failure, 'native_state_or_config_unavailable')
                    target = manager
                else:
                    target = self.inject(fixture, root, manager, ctx, backend, failure)
                self.assert_refused_without_writes(fixture, root, target, ctx, backend, 'off')
                target.close()
                ctx.get_config = type(ctx).get_config.__get__(ctx)
                ctx.settings.pop('limits.week_block_pct', None)
                healthy = fixture.manager(root, ctx=ctx, backend=backend)[0]
                self.assertTrue(fixture.call(healthy, 'mode off')['ok'])
                self.assertEqual(backend.read(), baseline)

    def test_healthy_retained_state_and_auxiliary_drift_keep_their_off_outcomes(self):
        for auxiliary in ('retained', 'active'):
            for drift in (False, True):
                with self.subTest(auxiliary=auxiliary, drift=drift), tempfile.TemporaryDirectory() as root:
                    fixture = self.fixture()
                    manager, ctx, backend, baseline = self.prepare(fixture, root, auxiliary)
                    if drift:
                        manager.auxiliary_compatible = lambda: dict(DRIFT)
                    result = fixture.call(manager, 'mode off')
                    self.assertTrue(result['ok'], result)
                    self.assertEqual(ctx.settings['mode'], 'off')
                    self.assertEqual(backend.read()['model'], baseline['model'])
                    pending = drift and auxiliary == 'active'
                    self.assertEqual(result['applied']['auxiliary']['restoration_pending'], pending)
                    self.assertEqual(backend.read() == baseline, not pending)
                    if pending:
                        manager.auxiliary_compatible = qualified
                        self.assertTrue(fixture.call(manager, 'mode off')['ok'])
                        self.assertEqual(backend.read(), baseline)

    def test_latch_with_auxiliary_drift_refuses_instead_of_using_the_fingerprint_exception(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = self.fixture()
            manager, ctx, backend, _ = self.prepare(fixture, root, 'active')
            target = self.inject(fixture, root, manager, ctx, backend, 'latch')
            target.auxiliary_compatible = lambda: dict(DRIFT)
            self.assert_refused_without_writes(fixture, root, target, ctx, backend, 'auto')


if __name__ == '__main__':
    unittest.main()
