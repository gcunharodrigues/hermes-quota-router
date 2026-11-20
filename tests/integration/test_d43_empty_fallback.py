"""D-43: no qualified candidate removes only a plugin-managed fallback."""
import copy
import unittest

import test_hqr38_fallback as support


class EmptyFallbackTests(unittest.TestCase):
    def test_auto_removes_managed_chains_without_rewriting_primary(self):
        harness = support.SafetyNetLifecycleTests()
        for manual_edit in (False, True):
            with self.subTest(manual_edit=manual_edit), harness.fixture() as (manager, backend, _, snapshots):
                harness.call(manager, 'config approve-map base')
                harness.call(manager, 'mode auto')
                if manual_edit:
                    backend.write({'fallback_providers': [support.OPUS]}, ())
                before = backend.read()
                expected = copy.deepcopy(before)
                if not manual_edit:
                    del expected['fallback_providers']
                del harness.option(expected)['fallback_providers']
                snapshots.update(openai_codex=None, anthropic=None)
                manager.cache.clear()
                harness.call(manager, 'apply')
                self.assertEqual(backend.read(), expected)

    def test_auto_does_not_clear_chain_that_plugin_has_not_applied(self):
        harness = support.SafetyNetLifecycleTests()
        config = copy.deepcopy(support.CONFIG)
        config['fallback_providers'] = [support.OPUS]
        with harness.fixture(config=config, openai_codex=None, anthropic=None) as (manager, backend, _, _):
            harness.call(manager, 'config approve-map base')
            harness.call(manager, 'mode auto')
            self.assertEqual(backend.read(), config)
