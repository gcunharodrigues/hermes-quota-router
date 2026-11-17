# Regression contract: decisions/hqr-20-amendment.md, D18/R2: refuse global transport overlays by field name.
import copy
import json
from pathlib import Path
import tempfile
import unittest

from quota_router import groups
from quota_router.apply import Engine, durable
from quota_router.render import render
from s2_fakes import codex, claude, reader_for
from s3_fakes import Backend, TARGET, qualified
import test_s3_lifecycle as fixtures

FIELD = 'model.openai_runtime'
PRIVATE = 'SYNTHETIC_PRIVATE_OVERLAY_VALUE'
CODEX = {'provider': 'openai-codex', 'model': 'gpt-6.1-sol', 'effort': 'high'}


class RuntimeOverlayTests(unittest.TestCase):
    def test_nonempty_global_overlay_blocks_conversation_and_subagent_groups_by_name_only(self):
        for value in ('codex_app_server', 'auto', PRIVATE, True, {'private': PRIVATE}):
            backend = Backend()
            backend.document['model']['openai_runtime'] = value
            for role in ('conversation', 'general'):
                with self.subTest(value_type=type(value).__name__, role=role):
                    self.assertEqual(groups.preconditions(backend.read(), role), [FIELD])
                    with self.assertRaisesRegex(ValueError, 'Group preconditions failed'):
                        groups.project(backend.read(), role)

    def test_absent_null_and_empty_overlay_do_not_block_native_default_groups(self):
        for value in (None, '', '   '):
            backend = Backend()
            for role in ('conversation', 'general'):
                self.assertEqual(groups.preconditions(backend.read(), role), [])
                backend.document['model']['openai_runtime'] = value
                self.assertEqual(groups.preconditions(backend.read(), role), [])

    def test_anthropic_to_codex_is_blocked_in_observe_enrollment_apply_and_status_without_value_leaks(self):
        helper = fixtures.AutoCommandTests()
        for value in ('codex_app_server', PRIVATE):
            with self.subTest(value_is_optin=value == 'codex_app_server'), tempfile.TemporaryDirectory() as root:
                manager, _, backend = helper.manager(root)
                self.addCleanup(manager.close)
                backend.document['model'].update(provider='anthropic', default='claude-opus-5-5', openai_runtime=value)
                manager.importer = lambda: reader_for(openai_codex=codex(10), anthropic=claude(100))
                before = backend.read()
                helper.call(manager, 'config approve-map base')
                helper.call(manager, 'mode observe')
                for command in ('status', 'explain', 'mode auto', 'apply', 'status', 'explain'):
                    payload = helper.call(manager, command)
                    for decision in (payload['decisions']['conversation'], payload['decisions']['routes']['general']):
                        self.assertEqual(decision['state'], 'group_blocked')
                        self.assertIsNone(decision.get('choice'))
                        self.assertIsNone(decision.get('would_change'))
                        self.assertIn(FIELD, decision['blocked_fields'])
                    text = render('explain' if command == 'explain' else 'status', payload)
                    self.assertIn(FIELD, text)
                    self.assertNotIn(value, json.dumps(payload) + text)
                    self.assertEqual(backend.read(), before)
                    self.assertEqual(backend.writes, [])
                retained = ''.join(p.read_text() for p in Path(root).glob('*.json'))
                self.assertNotIn(value, retained)

    def test_overlay_inserted_after_enrollment_is_rechecked_before_the_native_write(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            before = backend.read()
            def checkpoint(point):
                if point == 'journal':
                    backend.document['model']['openai_runtime'] = PRIVATE
            engine = Engine(root, backend, qualified, checkpoint)
            engine.cycle({'conversation': TARGET}, 100)
            expected = copy.deepcopy(before)
            expected['model']['openai_runtime'] = PRIVATE
            self.assertEqual(backend.read(), expected)
            self.assertEqual(backend.writes, [])
            self.assertEqual(engine.report(100)['groups_out']['conversation'], [FIELD])
            self.assertNotIn(PRIVATE, ''.join(p.read_text() for p in Path(root).glob('*.json')))

    def test_overlay_after_application_refuses_recovery_and_off_without_route_writes(self):
        for operation in ('recover', 'off'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as root:
                backend = Backend()
                engine = Engine(root, backend, qualified)
                engine.cycle({'conversation': TARGET}, 100)
                self.assertGreater(len(backend.writes), 0)
                if operation == 'recover':
                    entry = engine.state['groups']['conversation']
                    durable(Path(root) / 'journal.json', {'group': 'conversation', 'prior': entry['baseline'],
                            'target': entry['last'], 'at': 100})
                    backend.document['model']['default'] = entry['baseline']['model.default']['value']
                backend.document['model']['openai_runtime'] = PRIVATE
                before, writes = backend.read(), copy.deepcopy(backend.writes)
                reloaded = Engine(root, backend, qualified)
                reloaded.recover() if operation == 'recover' else reloaded.restore(200)
                self.assertEqual(backend.read(), before)
                self.assertEqual(backend.writes, writes)
                self.assertEqual(reloaded.report(200)['groups_out']['conversation'], [FIELD])
                self.assertNotIn(PRIVATE, ''.join(p.read_text() for p in Path(root).glob('*.json')))
