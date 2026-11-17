# Regression contract: decisions/hqr-20-amendment.md, D18/R1; provider alias dispatch is part of route identity.
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat, routes
from quota_router.apply import Engine, durable
from s3_fakes import Backend, TARGET
from test_s3_default_resolution import RUNTIME, SWITCH, synthetic_sources

AUTH = 'hermes_cli.auth'
NAME = '_PROVIDER_ALIASES'
KEY = AUTH + '.' + NAME


class ProviderAliasBindingTests(unittest.TestCase):
    def test_required_constants_include_provider_alias_dispatch(self):
        self.assertIn(NAME, compat.CONSTANTS.get(AUTH, ()))

    def test_alias_drift_blocks_apply_recovery_and_off_from_disk_or_loaded_table(self):
        for active in (False, True):
            with self.subTest(active=active), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                synthetic_sources(root)
                path = root / 'hermes_cli/auth.py'
                path.write_text(path.read_text() + '\n_PROVIDER_ALIASES = {"claude": "anthropic"}\n')
                wanted = ('hermes_cli.auth_constants', RUNTIME, SWITCH, 'hermes_cli.providers', AUTH)
                const_specs = {name: compat.CONSTANTS[name] for name in wanted if name in compat.CONSTANTS}
                backend_module = types.ModuleType('hermes_cli.config_backend')
                backend_module.__file__ = str(root / 'hermes_cli/config_backend.py')
                home_module = types.ModuleType('hermes_constants')
                home_module.get_hermes_home = lambda: root
                modules = {'hermes_cli.config_backend': backend_module, 'hermes_constants': home_module}
                if active:
                    auth = types.ModuleType(AUTH)
                    auth.__dict__[NAME] = {'claude': 'anthropic'}
                    modules[AUTH] = auth
                original = compat.collect_symbols
                expected = original(root, specs={}, constant_specs=const_specs)
                data = root / 'hosts.json'
                data.write_text(json.dumps({'hosts': [dict(expected, revision='a' * 40, label='synthetic')]}))
                with mock.patch.dict(sys.modules, modules), mock.patch.object(compat, 'DATA', data), \
                        mock.patch.object(compat, 'FUNCTIONS', {}), mock.patch.object(compat, 'CONSTANTS', const_specs), \
                        mock.patch.object(compat, 'native_revision', return_value='a' * 40), \
                        mock.patch.object(compat, 'collect_symbols', side_effect=lambda *a, **k: original(
                            root, specs={}, constant_specs=const_specs)):
                    self.assertTrue(compat._source_compatibility()['ok'], 'valid alias control')
                    backend = Backend()
                    engine = Engine(root / 'records', backend, compat._source_compatibility)
                    engine.cycle({'conversation': TARGET}, 100)
                    self.assertGreater(len(backend.writes), 0)
                    group = engine.state['groups']['conversation']
                    durable(root / 'records/journal.json', {'group': 'conversation', 'prior': group['baseline'],
                            'target': group['last'], 'at': 100})
                    backend.document['model']['default'] = group['baseline']['model.default']['value']
                    before, writes = backend.read(), copy.deepcopy(backend.writes)
                    retained = {p.name: p.read_bytes() for p in (root / 'records').iterdir()}
                    if active:
                        auth.__dict__[NAME]['openai-codex'] = 'anthropic'
                    else:
                        path.write_text(path.read_text().replace('{"claude": "anthropic"}',
                                                               '{"claude": "anthropic", "openai-codex": "anthropic"}'))
                    result = compat._source_compatibility()
                    self.assertFalse(result['ok'], result)
                    self.assertIn(KEY, result['reasons'])
                    engine.cycle({'conversation': TARGET}, 200)
                    self.assertFalse(engine.recover())
                    self.assertFalse(engine.restore(300))
                    self.assertEqual(backend.read(), before)
                    self.assertEqual(backend.writes, writes)
                    self.assertEqual({p.name: p.read_bytes() for p in (root / 'records').iterdir()}, retained)

    def test_requalified_alias_must_not_redirect_a_managed_provider(self):
        constants = json.loads(compat.DATA.read_text())['hosts'][0]['constants']
        for provider in ('openai-codex', 'anthropic'):
            with self.subTest(provider=provider):
                changed = copy.deepcopy(constants)
                changed[KEY] = {provider: provider}
                self.assertTrue(routes.mirror_matches(changed))
                changed[KEY][provider] = 'other-provider'
                self.assertFalse(routes.mirror_matches(changed))
