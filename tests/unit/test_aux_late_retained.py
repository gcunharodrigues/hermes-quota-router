# Contract: decisions/aux-plan.md, AUXP-04/H9/H13/H15c/H19: discover retained obligations inside the OFF lock.
"""Late publication by another Management instance, using only disposable native-contract fixtures."""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_aux_lifecycle as fixtures
from quota_router import storage
from quota_router.mapping import approved_auxiliary
from s3_fakes import qualified


class LateRetainedAuxiliaryTests(unittest.TestCase):
    def manager(self, root, **kwargs):
        fixture = fixtures.AuxiliaryLifecycleTests()
        self.addCleanup(fixture.doCleanups)
        return fixture.manager(root, **kwargs)

    def call(self, manager, command):
        return json.loads(manager.command(command + ' --json'))

    def pair(self, root):
        first, ctx, backend, _ = self.manager(root, enabled=False)
        baseline = backend.read()
        self.assertTrue(self.call(first, 'mode auto')['ok'])
        self.assertIsNone(first.aux_engine)
        self.assertFalse(Path(root, 'aux-state.json').exists())
        second, _, _, _ = self.manager(root, ctx=ctx, backend=backend)
        return first, second, ctx, backend, baseline

    def publish(self, second, ctx):
        previous = ctx.settings['auxiliary_map']
        ctx.settings['auxiliary_map'] = approved_auxiliary()
        ctx.settings['consumers.auxiliary'] = True
        self.publishing = True
        try:
            result = self.call(second, 'status')
        finally:
            self.publishing = False
            ctx.settings['auxiliary_map'] = previous
            ctx.settings['consumers.auxiliary'] = False
        self.assertTrue(result['ok'], result)
        self.assertEqual(len(result['applied']['auxiliary']['groups']), 11)
        self.assertTrue(all(entry['active'] for entry in result['applied']['auxiliary']['groups'].values()))

    @contextmanager
    def publication(self, timing, second, ctx):
        if timing == 'before_command':
            self.publish(second, ctx)
            yield
            return
        original = fcntl.flock
        published = False
        def acquire(handle, operation):
            nonlocal published
            if operation == fcntl.LOCK_EX and not published:
                published = True
                self.publish(second, ctx)
            return original(handle, operation)
        with patch.object(fcntl, 'flock', side_effect=acquire):
            yield
        self.assertTrue(published)

    def forbid_lookup(self):
        self.fail('OFF must not consult the map, catalog, registry or quota reader')

    def test_late_valid_auxiliary_restores_exactly_in_the_discovery_lock(self):
        for timing in ('before_command', 'before_lock'):
            with self.subTest(timing=timing), tempfile.TemporaryDirectory() as root:
                first, second, ctx, backend, baseline = self.pair(root)
                with self.publication(timing, second, ctx):
                    ctx.settings['auxiliary_map'] = {}
                    first.catalogs = first.auxiliary_registry = first.importer = first.sources = self.forbid_lookup
                    reads, restores = [], []
                    original_read = storage.read
                    def read(fd, name, *args, **kwargs):
                        if name in ('aux-state.json', 'aux-journal.json') and not getattr(self, 'publishing', False):
                            reads.append(first.engine._directory_fd)
                        return original_read(fd, name, *args, **kwargs)
                    original_restore = first.engine.restore_locked
                    def restore(now):
                        restores.append((first.engine._directory_fd, first.aux_engine._directory_fd if first.aux_engine else None))
                        return original_restore(now)
                    with patch.object(storage, 'read', side_effect=read), patch.object(first.engine, 'restore_locked', side_effect=restore):
                        result = self.call(first, 'mode off')
                self.assertTrue(result['ok'], result)
                self.assertEqual(backend.read(), baseline)
                self.assertEqual(ctx.settings['mode'], 'off')
                self.assertFalse(result['applied']['auxiliary']['restoration_pending'])
                self.assertFalse(Path(root, 'aux-journal.json').exists())
                self.assertTrue(reads)
                self.assertNotIn(None, reads)
                self.assertEqual(len(restores), 1)
                self.assertIsNotNone(restores[0][0])
                self.assertEqual(restores[0][0], restores[0][1])
                self.assertTrue(all(not entry['active'] for entry in result['applied']['auxiliary']['groups'].values()))

    def test_late_auxiliary_drift_keeps_pending_bytes_and_allows_main_off_then_retry(self):
        for timing in ('before_command', 'before_lock'):
            with self.subTest(timing=timing), tempfile.TemporaryDirectory() as root:
                first, second, ctx, backend, baseline = self.pair(root)
                with self.publication(timing, second, ctx):
                    first.auxiliary_compatible = lambda: {'ok': False, 'fingerprint_failure': True,
                                                        'reasons': ['agent.auxiliary_client.call_llm']}
                    result = self.call(first, 'mode off')
                self.assertTrue(result['ok'], result)
                self.assertEqual(ctx.settings['mode'], 'off')
                self.assertEqual(backend.read()['model'], baseline['model'])
                self.assertNotEqual(backend.read()['auxiliary'], baseline['auxiliary'])
                self.assertTrue(result['applied']['auxiliary']['restoration_pending'])
                self.assertEqual(len(result['applied']['auxiliary']['groups']), 11)
                self.assertTrue(all(entry['active'] for entry in result['applied']['auxiliary']['groups'].values()))
                retained = Path(root, 'aux-state.json').read_bytes()
                applied = deepcopy(backend.read()['auxiliary'])
                self.assertIn('restauração pendente', first.command('status'))
                self.assertIn('agent.auxiliary_client.call_llm', first.command('status'))
                self.assertEqual(Path(root, 'aux-state.json').read_bytes(), retained)
                self.assertEqual(backend.read()['auxiliary'], applied)
                first.auxiliary_compatible = qualified
                ctx.settings['auxiliary_map'] = {}
                first.catalogs = first.auxiliary_registry = first.importer = first.sources = self.forbid_lookup
                retried = self.call(first, 'mode off')
                self.assertTrue(retried['ok'], retried)
                self.assertFalse(retried['applied']['auxiliary']['restoration_pending'])
                self.assertEqual(backend.read(), baseline)
