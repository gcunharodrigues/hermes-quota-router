"""D-43: the operator can distinguish a retained route from an excluded group."""
import unittest

import test_hqr38_fallback as support


class RetentionStatusTests(unittest.TestCase):
    def test_unknown_incumbent_diagnostic_in_observe_and_auto(self):
        harness = support.SafetyNetLifecycleTests()
        for mode in ('observe', 'auto'):
            with self.subTest(mode=mode), harness.fixture() as (manager, backend, _, snapshots):
                harness.call(manager, 'config approve-map base')
                harness.call(manager, 'mode ' + mode)
                before = backend.read()
                snapshots['openai_codex'] = None
                manager.cache.clear()
                payload = harness.call(manager, 'apply' if mode == 'auto' else 'status')
                self.assertEqual(payload['decisions']['conversation']['reason'], 'incumbent_reading_unknown')
                self.assertNotIn('conversation', payload['routing_blocks'])
                text = manager.command('status')
                self.assertIn('cota da rota atual é desconhecida', text)
                self.assertNotIn('qualificação nativa indisponível', text)
                if mode == 'auto':
                    before['fallback_providers'] = [support.OPUS]
                    harness.option(before)['fallback_providers'] = [support.OPUS]
                self.assertEqual(backend.read(), before)
