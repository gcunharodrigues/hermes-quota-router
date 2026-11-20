"""HQR-38 safety net lifecycle through the native config seam (decisions/hqr-38-spec.md, D-28/D-29 and acceptance tests).

Disposable synthetic home, JSON storage primitive and injected readers; no real Hermes home, provider or credential.
"""
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/unit'))
from s2_fakes import NOW, claude, codex, reader_for
from s3_fakes import CONFIG, qualified
from test_s3_lifecycle import AutoContext
from quota_router.apply import NativeBackend
from quota_router.lifecycle import Management
from s3_native import install_layer

OPUS = {'provider': 'anthropic', 'model': 'claude-opus-5-5'}
SECRET = 'sk-synthetic-fallback-secret'


class SafetyNetLifecycleTests(unittest.TestCase):
    @contextmanager
    def fixture(self, config=CONFIG, **snapshots):
        snapshots = dict({'openai_codex': codex(10), 'anthropic': claude(80)}, **snapshots)
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules):
            root = Path(directory)
            with mock.patch.dict(os.environ, {'HERMES_HOME': str(root)}):
                install_layer()
                path = root / 'synthetic.json'
                path.write_text(json.dumps(config))
                backend = NativeBackend(path)
                manager = Management(AutoContext(), importer=lambda: reader_for(**snapshots),
                                     sources=lambda: (backend.read(), []), clock=lambda: NOW, profile=lambda: 'default',
                                     backend=backend, data_dir=root / 'data', compatible=qualified)
                try:
                    yield manager, backend, root, snapshots
                finally:
                    manager.close()

    def call(self, manager, command):
        result = json.loads(manager.command(command + ' --json'))
        self.assertTrue(result['ok'], result)
        return result

    def option(self, document):
        return document['delegation']['backends']['model_map']['options'][0]

    def test_auto_writes_both_chains_reads_them_back_and_off_restores_absence(self):
        with self.fixture() as (manager, backend, root, _):
            self.call(manager, 'config approve-map base')
            result = self.call(manager, 'mode auto')
            document = backend.read()
            self.assertEqual(document['model']['provider'], 'openai-codex')
            self.assertEqual(document['fallback_providers'], [{'provider': 'openai-codex', 'model': 'gpt-6.2-sol'}, OPUS])
            self.assertEqual(self.option(document)['fallback_providers'], [{'provider': 'openai-codex', 'model': 'gpt-6.2-sol'}, OPUS])
            self.assertEqual(result['decisions']['conversation']['safety_net']['chain'],
                             [{'provider': 'openai-codex', 'model': 'gpt-6.2-sol'}, OPUS])
            self.assertEqual(result['decisions']['routes']['general']['safety_net']['chain'],
                             [{'provider': 'openai-codex', 'model': 'gpt-6.2-sol'}, OPUS])
            applied = self.call(manager, 'status')['applied']
            for name in ('fallback:conversation', 'fallback:general'):
                self.assertTrue(applied['safety_net'][name]['active'], name)
            self.assertEqual(applied['groups_out'], {})
            state = json.loads((root / 'data/state.json').read_text())
            self.assertEqual(state['groups']['fallback:conversation']['baseline'], {'fallback_providers': {'present': False}})
            self.call(manager, 'mode off')
            self.assertEqual(backend.read(), CONFIG)

    def test_exhausted_peer_without_credits_writes_no_chain_over_an_absent_key(self):
        with self.fixture(anthropic=claude(100)) as (manager, backend, _, _snapshots):
            self.call(manager, 'config approve-map base')
            result = self.call(manager, 'mode auto')
            document = backend.read()
            self.assertEqual(document['fallback_providers'], [{'provider': 'openai-codex', 'model': 'gpt-6.2-sol'}])
            self.assertEqual(self.option(document)['fallback_providers'], [{'provider': 'openai-codex', 'model': 'gpt-6.2-sol'}])
            self.assertEqual(result['decisions']['conversation']['safety_net']['chain'],
                             [{'provider': 'openai-codex', 'model': 'gpt-6.2-sol'}])

    def test_chain_follows_the_next_decision_and_empties_a_present_key(self):
        config = copy.deepcopy(CONFIG)
        config['fallback_providers'] = [dict(OPUS, model='claude-sonnet-5-5')]
        with self.fixture(config=config) as (manager, backend, _, snapshots):
            self.call(manager, 'config approve-map base')
            self.call(manager, 'mode auto')
            self.assertEqual(backend.read()['fallback_providers'], [{'provider': 'openai-codex', 'model': 'gpt-6.2-sol'}, OPUS])
            snapshots['anthropic'] = claude(100)
            manager.cache.clear()
            self.call(manager, 'apply')
            self.assertEqual(backend.read()['fallback_providers'], [{'provider': 'openai-codex', 'model': 'gpt-6.2-sol'}])
            self.call(manager, 'mode off')
            self.assertEqual(backend.read(), config)

    def test_external_edit_excludes_the_safety_net_group_without_overwrite(self):
        with self.fixture() as (manager, backend, _, _snapshots):
            self.call(manager, 'config approve-map base')
            self.call(manager, 'mode auto')
            edited = [{'provider': 'openai-codex', 'model': 'gpt-6.1-terra'}]
            backend.write({'fallback_providers': edited}, ())
            manager.cache.clear()
            status = self.call(manager, 'apply')
            self.assertEqual(status['applied']['groups_out'], {'fallback:conversation': ['fallback_providers']})
            self.assertEqual(backend.read()['fallback_providers'], edited)
            self.call(manager, 'mode off')
            final = backend.read()
            self.assertEqual(final['fallback_providers'], edited)
            self.assertEqual(final['model'], CONFIG['model'])
            self.assertEqual(final['delegation'], CONFIG['delegation'])

    def test_credentials_in_a_chain_block_the_group_and_never_leave_the_config(self):
        config = copy.deepcopy(CONFIG)
        config['fallback_providers'] = [dict(OPUS, api_key=SECRET)]
        with self.fixture(config=config) as (manager, backend, root, _):
            self.call(manager, 'config approve-map base')
            self.call(manager, 'mode auto')
            status = manager.command('status --json')
            text = manager.command('status')
            self.assertEqual(backend.read()['fallback_providers'], config['fallback_providers'])
            self.assertEqual(json.loads(status)['applied']['groups_out']['fallback:conversation'], ['fallback_providers'])
            stored = ''.join(path.read_text() for path in (root / 'data').iterdir() if path.is_file())
            for output in (status, text, stored):
                self.assertNotIn(SECRET, output)
            self.call(manager, 'mode off')
            self.assertEqual(backend.read(), config)

    def test_status_text_shows_states_and_the_safety_net_in_portuguese(self):
        with self.fixture(openai_codex=codex(10, session_used=97)) as (manager, _backend, _, _snapshots):
            self.call(manager, 'config approve-map base')
            self.call(manager, 'mode auto')
            text = manager.command('status')
            self.assertIn('Codex: Pressionado', text)
            self.assertIn('Claude: Livre', text)
            self.assertIn('Rede de segurança', text)
            self.assertIn('tenta Codex gpt-6.2-sol', text)
            self.assertNotIn('fallback:conversation', text)


if __name__ == '__main__':
    unittest.main()
