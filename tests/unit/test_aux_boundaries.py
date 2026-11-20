# Contract: decisions/aux-plan.md, H1/H5b-H5e/H7/H13/H19/H21/H22 and OFF failure taxonomy.
"""Boundary regressions via the real synthetic Management fixture, without importing duplicate test IDs."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import test_aux_lifecycle as fixtures
from quota_router.mapping import approved_base
from s2_fakes import NOW, claude, codex


class AuxiliaryBoundaryTests(unittest.TestCase):
    def manager(self, root, **kwargs):
        fixture = fixtures.AuxiliaryLifecycleTests()
        self.addCleanup(fixture.doCleanups)
        return fixture.manager(root, **kwargs)

    def call(self, manager, command):
        return json.loads(manager.command(command + ' --json'))

    def test_observe_proposal_before_auxiliary_map_approval_is_visible_without_writes(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, b, _ = self.manager(root, enabled=False)
            ctx.settings['auxiliary_map'] = {}
            result = self.call(m, 'mode observe')
            item = result['decisions']['auxiliary']['tasks']['compression']
            self.assertEqual(item['state'], 'preview_only')
            self.assertEqual(item['choice'], 'anthropic')
            self.assertTrue(item['would_change'])
            self.assertEqual(b.writes, [])
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_blocked_conversation_uses_previous_source_without_recreating_main_preference(self):
        with tempfile.TemporaryDirectory() as root:
            m, _, b, snapshots = self.manager(root)
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            snapshots.update(openai_codex=codex(9, week_reset_h=120), anthropic=claude(10))
            b.document['model']['api_key'] = 'SYNTHETIC_PRIVATE_VALUE'
            m.cache.clear()
            result = self.call(m, 'status')
            source = result['decisions']['auxiliary']['source']
            self.assertEqual(source['path'], 'computed')
            self.assertEqual(source['choice'], 'anthropic')
            self.assertFalse(any(key[0] == 'conversation' for key in m.preferences))
            self.assertNotIn('conversation', m.preference_routes)
            self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', json.dumps(result))
            self.assertEqual(b.read()['auxiliary']['compression']['provider'], 'anthropic')

    def test_no_eligible_source_keeps_every_auxiliary_key_and_reports_model_states_and_resets(self):
        with tempfile.TemporaryDirectory() as root:
            m, _, b, snapshots = self.manager(root)
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            before, count = b.read(), len(b.writes)
            snapshots.update(openai_codex=codex(100), anthropic=claude(100))
            m.cache.clear()
            result = self.call(m, 'status')
            source = result['decisions']['auxiliary']['source']
            self.assertIsNone(source['choice'])
            self.assertEqual(source['path'], 'conversation')
            for task in result['decisions']['auxiliary']['tasks'].values():
                self.assertIsNone(task['choice'])
                self.assertTrue(task['resets'])
                self.assertEqual(task['model_state'], {'openai-codex': 'exhausted', 'anthropic': 'exhausted'})
            del before['fallback_providers']
            options = before['delegation']['backends']['model_map']['options']
            del next(option for option in options if option['name'] == 'general')['fallback_providers']
            self.assertEqual(b.read(), before)
            self.assertCountEqual(b.writes[count:], [({}, ('fallback_providers',)),
                                                     ({'delegation.backends.model_map.options': options}, ())])

    def test_no_conversation_pair_blocks_source_without_polluting_routing_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, b, _ = self.manager(root, conversation=False)
            del ctx.settings['roles']['conversation']
            before = b.read()['auxiliary']
            result = self.call(m, 'mode auto')
            self.assertTrue(result['ok'], result)
            self.assertEqual(result['decisions']['auxiliary']['source']['state'], 'source_map_not_approved')
            self.assertEqual(b.read()['auxiliary'], before)
            self.assertNotIn('auxiliary', result['routing_blocks'])

    def test_retained_auxiliary_fingerprint_drift_does_not_suspend_unrelated_main_decision(self):
        with tempfile.TemporaryDirectory() as root:
            m, _, b, snapshots = self.manager(root)
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            aux_before = b.read()['auxiliary']
            snapshots.update(openai_codex=codex(10), anthropic=claude(100))
            m.auxiliary_compatible = lambda: {'ok': False, 'fingerprint_failure': True, 'reasons': ['agent.auxiliary_client.call_llm']}
            m.cache.clear()
            result = self.call(m, 'status')
            self.assertEqual(b.read()['model']['provider'], 'openai-codex')
            self.assertEqual(b.read()['auxiliary'], aux_before)
            self.assertIsNone(result['decisions']['auxiliary']['tasks']['compression']['choice'])
            self.assertIn('agent.auxiliary_client.call_llm', m.command('status'))

    def test_non_fingerprint_auxiliary_failure_refuses_off_and_preserves_mode(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, b, _ = self.manager(root)
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            before = b.read()
            m.auxiliary_compatible = lambda: {'ok': False, 'reasons': ['synthetic_storage_contract_failure']}
            result = self.call(m, 'mode off')
            self.assertFalse(result['ok'])
            self.assertEqual(result['error'], 'Auto restoration incomplete')
            self.assertEqual(ctx.settings['mode'], 'auto')
            self.assertEqual(b.read(), before)

    def test_retired_map_task_restores_and_model_endpoint_block_does_not_echo_value(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, b, _ = self.manager(root, conversation=False)
            before = b.read()
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            del ctx.settings['auxiliary_map']['compression']
            self.assertTrue(self.call(m, 'status')['ok'])
            self.assertEqual(b.read()['auxiliary']['compression'], before['auxiliary']['compression'])
            self.assertTrue(self.call(m, 'mode off')['ok'])
            b.document['model'].update(provider='anthropic', base_url='SYNTHETIC_PRIVATE_ENDPOINT')
            result = self.call(m, 'mode auto')
            item = result['decisions']['auxiliary']['tasks']['approval']
            self.assertIsNone(item['choice'])
            self.assertEqual(item['blocked_fields'], ['model.base_url'])
            self.assertNotIn('SYNTHETIC_PRIVATE_ENDPOINT', json.dumps(result))

    def test_default_native_auxiliary_gate_is_not_bypassed_by_injected_main_qualification(self):
        from quota_router.compat import native_auxiliary_compatibility
        with tempfile.TemporaryDirectory() as root:
            m, _, b, _ = self.manager(root, auxiliary_compatible=native_auxiliary_compatibility)
            before = b.read()['auxiliary']
            result = self.call(m, 'mode auto')
            self.assertTrue(result['ok'], result)
            self.assertEqual(b.read()['auxiliary'], before)
            self.assertFalse(result['compatibility']['auxiliary']['ok'])
