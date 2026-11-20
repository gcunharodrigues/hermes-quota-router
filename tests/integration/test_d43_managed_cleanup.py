"""D-43: remove an unsafe managed chain without taking ownership of legacy fallback."""
import copy
import unittest

import test_hqr38_fallback as support
from s2_fakes import CREDITS_OK, claude, codex


class ManagedCleanupTests(unittest.TestCase):
    def test_retained_primary_drops_previous_paid_fallback(self):
        harness = support.SafetyNetLifecycleTests()
        with harness.fixture(openai_codex=codex(100, credits=CREDITS_OK), anthropic=claude(10)) as (manager, backend, _, snapshots):
            harness.call(manager, 'config approve-map base')
            harness.call(manager, 'mode auto')
            expected = backend.read()
            self.assertEqual(expected['model']['provider'], 'anthropic')
            self.assertIn('openai-codex', {cell['provider'] for cell in expected['fallback_providers']})
            del expected['fallback_providers']
            del harness.option(expected)['fallback_providers']
            snapshots['anthropic'] = None
            manager.cache.clear()
            result = harness.call(manager, 'apply')
            self.assertEqual(result['decisions']['conversation']['reason'], 'incumbent_reading_unknown')
            self.assertEqual(backend.read(), expected)

    def test_cleanup_preserves_and_reports_legacy_fallback(self):
        harness = support.SafetyNetLifecycleTests()
        config = copy.deepcopy(support.CONFIG)
        config['fallback_model'] = support.OPUS
        with harness.fixture(config=config) as (manager, backend, _, snapshots):
            harness.call(manager, 'config approve-map base')
            harness.call(manager, 'mode auto')
            expected = backend.read()
            del expected['fallback_providers']
            del harness.option(expected)['fallback_providers']
            snapshots.update(openai_codex=None, anthropic=None)
            manager.cache.clear()
            harness.call(manager, 'apply')
            self.assertEqual(backend.read(), expected)
            self.assertIn('O Hermes ainda pode usar o fallback legado', manager.command('status'))
