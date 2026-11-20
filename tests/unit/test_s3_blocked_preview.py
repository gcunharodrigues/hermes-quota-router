# Regression contract: decisions/hqr-20-amendment.md, D18 and AC-17: visible, faithful Auto exclusions.
import json
import tempfile
import unittest

from quota_router import groups
from quota_router.render import render
import test_s3_lifecycle as fixtures
from s2_fakes import codex, claude, reader_for


class BlockedPreviewTests(unittest.TestCase):
    def manager(self, root):
        helper = fixtures.AutoCommandTests()
        manager, ctx, backend = helper.manager(root)
        self.addCleanup(manager.close)
        helper.call(manager, 'config approve-map base')
        helper.call(manager, 'mode observe')
        return helper, manager, ctx, backend

    def test_preconditions_are_named_per_role_in_status_explain_and_auto_without_values(self):
        for field in ('base_url', 'api_mode', 'api_key', 'context_length'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                helper, manager, _, backend = self.manager(root)
                backend.document['model'][field] = 'SYNTHETIC_PRIVATE_ROUTE_VALUE'
                backend.document['delegation']['backends']['model_map']['options'][0][field] = 'SYNTHETIC_PRIVATE_ROUTE_VALUE'
                before = backend.read()
                for command in ('status', 'explain', 'mode auto', 'status', 'explain'):
                    payload = helper.call(manager, command)
                    for role, decision in [('conversation', payload['decisions']['conversation']),
                                           ('general', payload['decisions']['routes']['general'])]:
                        self.assertEqual(decision['state'], 'group_blocked')
                        self.assertIsNone(decision.get('choice'))
                        self.assertIsNone(decision.get('would_change'))
                        self.assertIsNone(decision.get('proposal_change'))
                        self.assertTrue(any(name.endswith('.' + field) for name in decision['blocked_fields']))
                        self.assertIn(role, payload['routing_blocks'])
                    text = render('explain' if command == 'explain' else 'status', payload)
                    self.assertIn('conversation fora do Auto', text)
                    self.assertIn('general fora do Auto', text)
                    self.assertIn('.' + field, text)
                    self.assertNotIn('SYNTHETIC_PRIVATE_ROUTE_VALUE', json.dumps(payload) + text)
                    self.assertNotIn('Recomendação: Claude', text)
                    self.assertEqual(backend.read(), before)

    def test_observe_reports_null_restore_limit_and_native_compatibility_gate_without_writes(self):
        for gate in ('null', 'compatibility', 'settings', 'backend'):  # D-37: no profile gate
            with self.subTest(gate=gate), tempfile.TemporaryDirectory() as root:
                helper, manager, ctx, backend = self.manager(root)
                if gate == 'null':
                    backend.can_store_null = False
                    backend.document['model']['base_url'] = None
                elif gate == 'compatibility':
                    manager.compatible = lambda: {'ok': False, 'reasons': ['native_symbol_changed']}
                elif gate == 'settings':
                    ctx.settings['limits.week_block_pct'] = 999
                elif gate == 'profile':
                    manager.profile = lambda: 'not-enrolled'
                else:
                    manager.compatible = lambda: {'ok': True, 'reasons': [], 'subagents': {'ok': False}}
                before = backend.read()
                payload = helper.call(manager, 'explain')
                role = 'general' if gate == 'backend' else 'conversation'
                decision = payload['decisions']['routes'][role] if role == 'general' else payload['decisions'][role]
                self.assertIsNone(decision.get('would_change'))
                self.assertIsNone(decision.get('choice'))
                self.assertIn(role, payload['routing_blocks'])
                self.assertIn(role + ' fora do Auto', render('explain', payload))
                self.assertEqual(backend.read(), before)
                self.assertEqual(backend.writes, [])

    def test_detected_external_edit_is_not_advertised_as_a_pending_change(self):
        with tempfile.TemporaryDirectory() as root:
            helper, manager, _, backend = self.manager(root)
            helper.call(manager, 'mode auto')
            backend.document['model']['default'] = 'gpt-6.1-terra'
            before = backend.read()
            for command in ('status', 'explain'):
                payload = helper.call(manager, command)
                self.assertEqual(payload['decisions']['conversation']['state'], 'group_blocked')
                self.assertIsNone(payload['decisions']['conversation'].get('would_change'))
                self.assertIn('model.default', payload['routing_blocks']['conversation']['fields'])
                self.assertIn('conversation fora do Auto', render(command, payload))
                self.assertEqual(backend.read(), before)

    def test_catalog_and_unmapped_role_gates_are_visible_per_role(self):
        for gate in ('catalog', 'map'):
            with self.subTest(gate=gate), tempfile.TemporaryDirectory() as root:
                helper, manager, ctx, backend = self.manager(root)
                if gate == 'catalog':
                    manager.catalogs = lambda: {'anthropic': ['claude-sonnet-5-5']}
                else:
                    ctx.settings['roles'].pop('general')
                payload = helper.call(manager, 'explain')
                self.assertIn('general', payload['routing_blocks'])
                self.assertIsNone(payload['decisions']['routes']['general'].get('would_change'))
                self.assertIn('general fora do Auto', render('explain', payload))

    def test_endpoint_presence_change_invalidates_observed_preference_even_for_same_provider(self):
        with tempfile.TemporaryDirectory() as root:
            helper, manager, _, backend = self.manager(root)
            usage = {'openai_codex': codex(30, week_reset_h=84), 'anthropic': claude(10, week_reset_h=84)}
            manager.importer = lambda: reader_for(**usage)
            manager.cache.clear()
            helper.call(manager, 'explain')
            usage['openai_codex'] = codex(5, week_reset_h=84)
            manager.cache.clear()
            self.assertEqual(helper.call(manager, 'explain')['decisions']['routes']['general']['choice'], 'anthropic')
            backend.document['delegation']['backends']['model_map']['options'][0].update(
                base_url='https://chatgpt.com/backend-api/codex', api_mode='codex_responses')
            payload = helper.call(manager, 'mode auto')
            self.assertEqual(payload['decisions']['routes']['general']['choice'], 'openai-codex')
            self.assertEqual(groups.option(backend.read(), 'general')['provider'], 'openai-codex')
