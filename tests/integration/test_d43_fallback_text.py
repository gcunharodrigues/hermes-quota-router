"""D-43: the status distinguishes applied fallbacks from the primary decision."""
import unittest

import test_hqr38_fallback as support


class FallbackTextTests(unittest.TestCase):
    def test_status_shows_applied_chain_with_retained_primary_and_after_clear(self):
        harness = support.SafetyNetLifecycleTests()
        with harness.fixture() as (manager, _, _, snapshots):
            harness.call(manager, 'config approve-map base')
            harness.call(manager, 'mode auto')
            snapshots['openai_codex'] = None
            manager.cache.clear()
            harness.call(manager, 'apply')
            text = manager.command('status')
            self.assertIn('**Fallback gerenciado aplicado**', text)
            self.assertIn('Claude claude-opus-5-5', text)
            self.assertIn('cota da rota atual é desconhecida', text)
            snapshots['anthropic'] = None
            manager.cache.clear()
            harness.call(manager, 'apply')
            self.assertIn('sem entradas gerenciadas', manager.command('status'))
