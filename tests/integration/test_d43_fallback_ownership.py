"""D-43: a manual fallback matching a decision is not owned by the plugin."""
import copy
import tempfile
import unittest

import test_hqr38_fallback as support
from quota_router.apply import Engine
from s3_fakes import Backend, qualified


class FallbackOwnershipTests(unittest.TestCase):
    def test_engine_refuses_to_clear_equal_manual_chain(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            backend.document['fallback_providers'] = [support.OPUS]
            engine = Engine(root, backend, qualified)
            engine.cycle({'fallback:conversation': {'chain': [support.OPUS]}}, 100)
            engine.cycle({'fallback:conversation': {'chain': []}}, 101)
            self.assertEqual(backend.read()['fallback_providers'], [support.OPUS])
            self.assertEqual(backend.writes, [])

    def test_equal_manual_chain_is_not_cleared_with_or_without_legacy(self):
        harness = support.SafetyNetLifecycleTests()
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                config = copy.deepcopy(support.CONFIG)
                config['fallback_providers'] = [{'provider': 'openai-codex', 'model': 'gpt-6.2-sol'}, support.OPUS]
                harness.option(config)['fallback_providers'] = copy.deepcopy(config['fallback_providers'])
                if legacy:
                    config['fallback_model'] = support.OPUS
                with harness.fixture(config=config) as (manager, backend, _, snapshots):
                    harness.call(manager, 'config approve-map base')
                    harness.call(manager, 'mode auto')
                    before = backend.read()
                    self.assertEqual(before['fallback_providers'], config['fallback_providers'])
                    self.assertEqual(harness.option(before)['fallback_providers'], harness.option(config)['fallback_providers'])
                    snapshots.update(openai_codex=None, anthropic=None)
                    manager.cache.clear()
                    harness.call(manager, 'apply')
                    self.assertEqual(backend.read(), before)
