# Regression contract: decisions/hqr-20-amendment.md, D18/AC-17: returned preview reflects gates checked during apply.
import copy
import tempfile
import unittest

import test_s3_lifecycle as fixtures
from quota_router.render import render


class FinalGateTests(unittest.TestCase):
    def test_group_excluded_after_preview_is_not_advertised_by_the_returned_auto_status(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, _, backend = helper.manager(root)
            self.addCleanup(manager.close)
            helper.call(manager, 'config approve-map base')
            def source_then_edit():
                snapshot = backend.read()
                backend.document['model']['base_url'] = 'https://synthetic.invalid/late-edit'
                return snapshot, []
            manager.sources = source_then_edit
            result = helper.call(manager, 'mode auto')
            decision = result['decisions']['conversation']
            self.assertEqual(decision['state'], 'group_blocked')
            self.assertIsNone(decision.get('choice'))
            self.assertIsNone(decision.get('would_change'))
            self.assertEqual(result['routing_blocks']['conversation']['fields'], ['model.base_url'])
            self.assertIn('conversation fora do Auto', render('status', result))
            self.assertNotIn('late-edit', repr(result))
            self.assertEqual(backend.read()['model']['provider'], 'openai-codex')

    def test_last_native_qualification_result_overrides_an_earlier_ready_result(self):
        import inspect
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, _, _ = helper.manager(root)
            self.addCleanup(manager.close)
            helper.call(manager, 'config approve-map base')
            def compatible():
                # Only the final source check in status observes drift; earlier enrollment checks still pass.
                if inspect.currentframe().f_back.f_code.co_name == 'status':
                    return {'ok': False, 'reasons': ['native_function_changed']}
                return {'ok': True, 'reasons': []}
            manager.compatible = compatible
            result = helper.call(manager, 'mode auto')
            self.assertFalse(result['compatibility']['source_qualified'])
            self.assertFalse(result['auto_available'])
            self.assertEqual(result['compatibility']['auto'], 'unavailable')
            self.assertIsNone(result['decisions']['conversation'].get('would_change'))

    def test_qualification_lost_between_preview_and_apply_suppresses_all_announced_changes(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, _, backend = helper.manager(root)
            self.addCleanup(manager.close)
            helper.call(manager, 'config approve-map base')
            ready = {'ok': True}
            manager.compatible = lambda: {'ok': ready['ok'], 'reasons': [] if ready['ok'] else ['native_function_changed']}
            snapshot = backend.read()
            manager.sources = lambda: (copy.deepcopy(snapshot), [])
            original = backend.read
            def read_after_source():
                ready['ok'] = False
                return original()
            backend.read = read_after_source
            result = helper.call(manager, 'mode auto')
            self.assertFalse(result['auto_available'])
            for role, decision in [('conversation', result['decisions']['conversation']),
                                   ('general', result['decisions']['routes']['general'])]:
                self.assertEqual(decision['state'], 'group_blocked')
                self.assertIsNone(decision.get('choice'))
                self.assertIsNone(decision.get('would_change'))
                self.assertIn('native_function_changed', result['routing_blocks'][role]['reasons'])
            self.assertEqual(backend.writes, [])
            self.assertNotIn('Recomendação: Claude', render('status', result))
