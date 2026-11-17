"""Scenario -> write/no-write proof through the native config seam in a disposable synthetic home."""
import copy
from contextlib import contextmanager
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/unit'))
from s2_fakes import CREDITS_EMPTY, CREDITS_OK, NOW, claude, codex, reader_for
from s3_fakes import CONFIG, qualified
from test_s3_lifecycle import AutoContext
from quota_router.apply import Engine, NativeBackend
from quota_router.groups import project, target
from quota_router.mapping import approved_base
from quota_router.lifecycle import Management
from s3_native import install_layer


class ScenarioTests(unittest.TestCase):
    @contextmanager
    def managed_fixture(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules):
            root = Path(directory)
            with mock.patch.dict(os.environ, {'HERMES_HOME': str(root)}):
                install_layer()
                path = root / 'synthetic.json'
                path.write_text(json.dumps(CONFIG))
                backend = NativeBackend(path)
                manager = Management(AutoContext(), importer=lambda: reader_for(openai_codex=codex(100), anthropic=claude(10)),
                                     sources=lambda: (backend.read(), []), clock=lambda: NOW, profile=lambda: 'default',
                                     backend=backend, data_dir=root / 'data', compatible=qualified)
                try:
                    yield manager, backend, path
                finally:
                    manager.close()

    def call(self, manager, command):
        result = json.loads(manager.command(command + ' --json'))
        self.assertTrue(result['ok'], result)
        return result

    def test_management_consumer_toggles_restore_independently_and_reenroll(self):
        with self.managed_fixture() as (manager, backend, path):
            baseline = backend.read()
            self.call(manager, 'config approve-map base')
            self.call(manager, 'mode auto')
            anthropic = backend.read()
            self.call(manager, 'config set consumers.conversation false')
            self.call(manager, 'apply')
            self.assertEqual(project(backend.read(), 'conversation'), project(baseline, 'conversation'))
            self.assertEqual(project(backend.read(), 'general'), project(anthropic, 'general'))
            backend.write({'model.default': 'gpt-6.1-terra', 'agent.reasoning_effort': 'low'}, ())
            new_baseline = backend.read()
            self.call(manager, 'config set consumers.conversation true')
            self.call(manager, 'apply')
            self.assertEqual(project(backend.read(), 'conversation'), project(anthropic, 'conversation'))
            self.call(manager, 'config set consumers.subagents false')
            self.call(manager, 'apply')
            self.assertEqual(project(backend.read(), 'general'), project(baseline, 'general'))
            self.assertEqual(project(backend.read(), 'conversation'), project(anthropic, 'conversation'))
            self.call(manager, 'config set consumers.subagents true')
            self.call(manager, 'apply')
            self.assertEqual(project(backend.read(), 'general'), project(anthropic, 'general'))
            self.call(manager, 'mode off')
            final = backend.read()
            self.assertEqual(project(final, 'conversation'), project(new_baseline, 'conversation'))
            self.assertEqual(project(final, 'general'), project(baseline, 'general'))

    def test_native_option_fallback_edits_survive_apply_and_off(self):
        from s3_fakes import TARGET
        with self.managed_fixture() as (manager, backend, path):
            engine = Engine(path.parent / 'option-data', backend, qualified)
            baseline = backend.read()
            engine.cycle({'general': TARGET}, 100)
            options = backend.read()['delegation']['backends']['model_map']['options']
            options[0].update(fallbacks=['edited'], description='edited description', custom='preserved')
            backend.write({'delegation.backends.model_map.options': options}, ())
            for action in (lambda: engine.cycle({'general': TARGET}, 200), lambda: engine.restore(300)):
                action()
                reread = backend.read()['delegation']['backends']['model_map']['options']
                self.assertEqual(reread[0]['fallbacks'], ['edited'])
                self.assertEqual(reread[0]['description'], 'edited description')
                self.assertEqual(reread[0]['custom'], 'preserved')
                self.assertEqual(reread[1:], baseline['delegation']['backends']['model_map']['options'][1:])
                self.assertNotIn('general', engine.report(301)['groups_out'])
            self.assertEqual(project(backend.read(), 'general'), project(baseline, 'general'))

    def test_s3_quota_scenarios_apply_only_eligible_approved_groups(self):
        cases = [
            ('A1', codex(10), claude(80), {}, 'openai-codex'),
            ('A2', codex(100, credits=CREDITS_OK), claude(10), {}, 'anthropic'),
            ('A3', codex(10), claude(100), {}, 'openai-codex'),
            ('A4', codex(100, credits=CREDITS_OK), claude(100), {}, 'openai-codex'),
            ('A5', codex(100, credits=CREDITS_OK), claude(100), {'credits.openai-codex': False}, None),
            # decisions/hqr-38-spec.md, D-31: a pressed 5 h window is a candidate when no provider is free.
            ('A6', codex(100), claude(10, session_used=96), {}, 'anthropic'),
            ('A7', codex(10, week_reset_h=-1), claude(100), {}, None),
            ('A8', codex(10, fetched_at=NOW - timedelta(hours=1)), claude(100), {}, None),
            ('B1', codex(10), claude(80), {'models.fable': False}, 'openai-codex'),
            ('B2', codex(10), claude(80), {'models.fable': True}, 'openai-codex'),
            ('B5', codex(10, astra=False), claude(80), {'models.astra': True}, 'openai-codex'),
            ('A9', RuntimeError('SYNTHETIC_PRIVATE_ERROR'), claude(100), {}, None),
            ('A11', codex(100, credits=CREDITS_EMPTY), claude(100), {}, None),
            ('B3-B4', codex(10, astra=True), claude(10), {'models.fable': True, 'models.astra': True}, 'openai-codex'),
        ]
        for name, c, a, settings, expected in cases:
            with self.subTest(scenario=name), tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules):
                root = Path(directory)
                with mock.patch.dict(os.environ, {'HERMES_HOME': str(root)}):
                    layer = install_layer()
                    config = copy.deepcopy(CONFIG)
                    config['delegation']['backends']['model_map']['options'].append({'name': 'unmapped', 'model': 'gpt-6.1-terra'})
                    path = root / 'synthetic.json'
                    path.write_text(json.dumps(config))
                    ctx = AutoContext(settings)
                    reader = reader_for(openai_codex=c, anthropic=a)
                    m = Management(ctx, importer=lambda: reader, sources=lambda: (json.loads(path.read_text()), []),
                                   clock=lambda: NOW, profile=lambda: 'default', backend=NativeBackend(path),
                                   data_dir=root / 'data', compatible=qualified)
                    json.loads(m.command('config approve-map base --json'))
                    result = json.loads(m.command('mode auto --json'))
                    self.assertTrue(result['ok'])
                    applied = json.loads(path.read_text())
                    if expected is None:
                        self.assertEqual(applied, config)
                    else:
                        for role in ('conversation', 'general'):
                            wanted = dict(approved_base()[role][expected], provider=expected)
                            self.assertEqual(project(applied, role), target(role, wanted))
                    self.assertEqual(applied['delegation']['backends']['model_map']['options'][1:],
                                     config['delegation']['backends']['model_map']['options'][1:])
                    self.assertEqual(applied['cron'], config['cron'])
                    self.assertNotIn('SYNTHETIC_PRIVATE_ERROR', json.dumps(result))
                    m.close()

    def test_a13_returns_conversation_to_principal_and_cron_toggle_has_no_write_group(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules):
            root = Path(directory)
            install_layer()
            path = root / 'synthetic.json'
            path.write_text(json.dumps(CONFIG))
            ctx = AutoContext()
            snapshots = {'openai_codex': codex(100), 'anthropic': claude(10)}
            m = Management(ctx, importer=lambda: reader_for(**snapshots), sources=lambda: (json.loads(path.read_text()), []),
                           clock=lambda: NOW, profile=lambda: 'default', backend=NativeBackend(path), data_dir=root / 'data', compatible=qualified)
            m.command('config approve-map base --json')
            m.command('config set consumers.cron false --json')
            m.command('mode auto --json')
            self.assertEqual(json.loads(path.read_text())['model']['provider'], 'anthropic')
            for used, provider in ((15, 'anthropic'), (12, 'anthropic'), (11, 'openai-codex')):
                snapshots.update(openai_codex=codex(used, week_reset_h=84), anthropic=claude(20, week_reset_h=84))
                for _ in range(3):
                    m.cache.clear()
                    result = json.loads(m.command('apply --json'))
                    applied = json.loads(path.read_text())
                    self.assertEqual(project(applied, 'conversation'), target('conversation',
                        dict(approved_base()['conversation']['openai-codex'], provider='openai-codex')))
                    self.assertEqual(project(applied, 'general'), target('general',
                        dict(approved_base()['general'][provider], provider=provider)))
            state = json.loads((root / 'data/state.json').read_text())
            self.assertNotIn('cron', state['groups'])
            self.assertIn('sem efeito', result['cron_origins']['consumers.cron'])
            m.close()


if __name__ == '__main__':
    unittest.main()
