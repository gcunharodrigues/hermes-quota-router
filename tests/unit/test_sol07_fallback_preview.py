"""SOL-07: Observe and final reflection share fallback gates; no Engine transaction is executed."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from s2_fakes import NOW, claude, codex, reader_for
from s3_fakes import Backend, qualified
from quota_router import groups
from quota_router.lifecycle import Management
from quota_router.mapping import approved_base
from quota_router.render import render, safety_net_lines

SOL = {'provider': 'openai-codex', 'model': 'gpt-6.1-sol'}
OPUS = {'provider': 'anthropic', 'model': 'claude-opus-5-5'}
PRIVATE = 'REFUSED_SYNTHETIC_VALUE'


class Context:
    def __init__(self):
        self.values = {'mode': 'observe', 'roles': approved_base()}

    def get_config(self, key, default=None):
        return copy.deepcopy(self.values.get(key, default))


class ReportOnly:
    def __init__(self, report):
        self.value = report

    def report(self, _):
        return copy.deepcopy(self.value)


class FallbackPreviewTests(unittest.TestCase):
    def manager(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        backend = Backend()
        backend.can_store_null = False
        reader = reader_for(openai_codex=codex(10), anthropic=claude(30))
        manager = Management(Context(), importer=lambda: reader, sources=lambda: (backend.read(), []), clock=lambda: NOW,
                             profile=lambda: 'default', backend=backend, data_dir=Path(root.name) / 'absent',
                             compatible=qualified, catalogs=lambda: {})
        self.assertIsNone(manager.engine)
        return manager, backend

    def test_null_and_invalid_projection_block_only_the_safety_net_without_value_disclosure(self):
        for value in (None, [dict(OPUS, model=PRIVATE)], [dict(OPUS, api_key=PRIVATE)]):
            with self.subTest(value=value):
                manager, backend = self.manager()
                backend.document['fallback_providers'] = value
                before = backend.read()
                result = manager.explain()
                decision = result['decisions']['conversation']
                self.assertEqual(decision['state'], 'decided')
                self.assertEqual(decision['choice'], 'openai-codex')
                self.assertEqual(decision['safety_net'].get('state'), 'group_blocked')
                self.assertIsNone(decision['safety_net']['chain'])
                self.assertIn('fallback:conversation', result['routing_blocks'])
                self.assertNotIn(PRIVATE, json.dumps(result) + render('explain', result))
                self.assertEqual(backend.read(), before)
                self.assertEqual(backend.writes, [])

    def test_external_edit_is_compared_against_retained_safety_net_not_route_projection(self):
        manager, backend = self.manager()
        document = backend.read()
        document['fallback_providers'] = [SOL, OPUS]
        last = groups.project(document, 'fallback:conversation')
        manager.engine = ReportOnly({'auto_declared': True, 'safety_net': {
            'fallback:conversation': {'active': True, 'values': last}}, 'groups': {}, 'groups_out': {}})
        backend.document['fallback_providers'] = [OPUS]
        result = manager.explain()
        decision = result['decisions']['conversation']
        self.assertEqual(decision['state'], 'decided')
        self.assertEqual(decision['safety_net'].get('state'), 'group_blocked')
        self.assertIsNone(decision['safety_net']['chain'])
        self.assertEqual(result['routing_blocks']['fallback:conversation']['fields'], ['fallback_providers'])
        self.assertEqual(backend.writes, [])

    def test_legacy_outside_eligible_chain_blocks_preview_without_editing_it(self):
        manager, backend = self.manager()
        backend.document['fallback_model'] = dict(OPUS, model='claude-sonnet-5-5')
        result = manager.explain()
        self.assertEqual(result['decisions']['conversation']['safety_net'].get('state'), 'group_blocked')
        self.assertEqual(result['routing_blocks']['fallback:conversation']['fields'], ['fallback_model'])
        self.assertEqual(backend.writes, [])

    def test_final_fallback_exclusion_cancels_chain_without_blocking_intact_route(self):
        manager, _ = self.manager()
        result = manager.explain()
        result['applied'] = {'auto_declared': True, 'groups_out': {'fallback:conversation': ['fallback_providers']}}
        manager.reflect_final_blocks(result, {'ok': True}, manager.settings()[0])
        decision = result['decisions']['conversation']
        self.assertEqual(decision['state'], 'decided')
        self.assertEqual(decision['safety_net'].get('state'), 'group_blocked')
        self.assertIsNone(decision['safety_net']['chain'])
        self.assertIn('fallback:conversation', result['routing_blocks'])
        self.assertIn('rede de segurança da conversa fora do Auto', render('explain', result))

    def test_render_explains_shared_chain_without_retrying_auto_primary_against_itself(self):
        decisions = {'conversation': {'choice': 'openai-codex', 'safety_net': {'chain': [SOL, OPUS], 'excluded': {}}},
                     'routes': {}, 'cron': {'state': 'follows_conversation'}}
        text = '\n'.join(safety_net_lines(decisions, False))
        self.assertIn('o Hermes tenta Claude', text)
        self.assertNotIn('o Hermes tenta Codex', text)
        self.assertIn('primário efetivo', text)
