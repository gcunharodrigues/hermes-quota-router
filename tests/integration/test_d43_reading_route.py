"""D-43: unusable quota evidence does not displace the configured provider."""
import unittest

import test_hqr38_fallback as support
from quota_router import readings


class ReadingRouteTests(unittest.TestCase):
    def test_unknown_incumbent_is_retained_but_confirmed_exhaustion_can_switch(self):
        harness = support.SafetyNetLifecycleTests()
        with harness.fixture() as (manager, backend, _, snapshots):
            harness.call(manager, 'config approve-map base')
            harness.call(manager, 'mode auto')
            before = backend.read()
            malformed = support.codex(10)
            raw = malformed.raw
            assert raw is not None
            raw['rate_limit']['tertiary_window'] = {'used_tokens': 10}
            snapshots['openai_codex'] = malformed
            manager.cache.clear()
            result = harness.call(manager, 'apply')
            self.assertEqual(result['decisions']['conversation']['reason'], 'incumbent_reading_unknown')
            before['fallback_providers'] = [support.OPUS]
            harness.option(before)['fallback_providers'] = [support.OPUS]
            self.assertEqual(backend.read(), before)
            snapshots['openai_codex'] = support.codex(100)
            snapshots['anthropic'] = support.claude(10)
            manager.cache.clear()
            harness.call(manager, 'apply')
            self.assertEqual(backend.read()['model']['provider'], 'anthropic')

    def test_timeout_snapshot_is_visible_but_does_not_drive_a_pacing_switch(self):
        harness = support.SafetyNetLifecycleTests()
        with harness.fixture(openai_codex=support.codex(60)) as (manager, backend, _, snapshots):
            harness.call(manager, 'config approve-map base')
            harness.call(manager, 'mode auto')
            before = backend.read()
            snapshots.update(openai_codex=readings._NativeFailure({'kind': 'timeout'}),
                             anthropic=support.claude(10))
            manager.cache.clear()
            result = harness.call(manager, 'apply')
            self.assertEqual(result['decisions']['routes']['general']['reason'], 'fresh_quota_pair_required')
            self.assertEqual(backend.read(), before)
