# Regression contract: decisions/hqr-20-amendment.md, D18/R1: default resolution drift blocks every write path.
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat
from quota_router.apply import Engine, durable
from s3_fakes import Backend, TARGET

RUNTIME = 'hermes_cli.runtime_provider'
SWITCH = 'hermes_cli.model_switch'
# The normal /model path has no explicit credential and must not attest only its explicit builders.
REQUIRED = {
    RUNTIME: ('_explicit_codex', '_explicit_anthropic', 'resolve_runtime_provider', 'resolve_requested_provider',
              '_ladder_rungs', '_get_model_config', 'load_config', '_runtime', '_resolve_requested_shortcuts',
              '_named_custom_rung', '_local_endpoint_bypass', '_resolve_explicit_runtime', '_resolve_from_pool',
              '_resolve_runtime_from_pool_entry', '_pool_entry_mode_and_url', '_pool_entry_base_url', '_effective_model',
              '_finalize_base_url', '_resolve_oauth_runtime', '_OAuthRuntimeSpec', '_anthropic_env_runtime',
              '_anthropic_cfg_base_url', '_anthropic_base_url_override_ok', '_config_base_url_for_provider',
              '_cfg_provider', '_same_registered_provider', '_maybe_apply_codex_app_server_runtime', '_detect_api_mode_for_url'),
    'hermes_cli.auth_codex': ('resolve_codex_runtime_credentials', '_codex_runtime_result', '_codex_base_url',
                            '_codex_pool_route_base_url'),
    'hermes_cli.auth': ('resolve_provider', '_plugin_aliases', '_registry_lookup'),
    SWITCH: ('_Switch.resolve_runtime', '_creds_for_switched_provider', '_creds_for_current_provider',
             '_resolve_switch_credentials', '_build_switch_result', 'model_derived_api_mode', 'switch_model'),
    'hermes_cli.providers': ('determine_api_mode', 'host_mandated_api_mode', 'is_actual_route', 'is_official_openai_host'),
}
TABLES = {RUNTIME: ('_OAUTH_RUNTIME_PROVIDERS', '_POOL_ENTRY_SIMPLE_MODES'),
          SWITCH: ('_PROVIDER_API_MODE_OVERRIDES',)}
TABLE_SOURCE = {
    RUNTIME: '''
_POOL_ENTRY_SIMPLE_MODES = {"openai-codex": ("codex_responses", DEFAULT_CODEX_BASE_URL),
                            "unrelated": ("mode", lambda: forbidden())}
_OAUTH_RUNTIME_PROVIDERS = {
    "openai-codex": _OAuthRuntimeSpec(lambda: resolve_codex_runtime_credentials(), "codex_responses",
                                    "hermes-auth-store", "last_refresh", "unavailable"),
    "unrelated": _OAuthRuntimeSpec(lambda: forbidden(), "other", "source", "expiry", "unavailable")}
''',
    SWITCH: '_PROVIDER_API_MODE_OVERRIDES = {**dict.fromkeys(("nous",), forbidden)}\n',
}


def synthetic_sources(root):
    constants = json.loads(compat.DATA.read_text())['hosts'][0]['constants']
    modules = set(REQUIRED) | {'hermes_cli.auth_constants'}
    for module in modules:
        path = root.joinpath(*module.split('.')).with_suffix('.py')
        path.parent.mkdir(parents=True, exist_ok=True)
        source = ''
        for name in REQUIRED.get(module, ()):
            if '.' in name:
                owner, method = name.split('.')
                source += f'class {owner}:\n    def {method}(self):\n        return "baseline"\n\n'
            elif name == '_OAuthRuntimeSpec':
                source += 'class _OAuthRuntimeSpec:\n    pass\n\n'
            else:
                source += f'def {name}():\n    return "baseline"\n\n'
        for key, value in constants.items():
            prefix, name = key.rsplit('.', 1)
            if prefix == module and name not in TABLES.get(module, ()):
                source += name + ' = ' + repr(value) + '\n'
        source += TABLE_SOURCE.get(module, '')
        path.write_text(source)


class DefaultResolutionTests(unittest.TestCase):
    def test_required_set_covers_nonexplicit_builders_selection_and_overlay(self):
        for module, names in REQUIRED.items():
            with self.subTest(module=module):
                self.assertTrue(set(names) <= set(compat.FUNCTIONS.get(module, ())), module)
        for module, names in TABLES.items():
            with self.subTest(module=module):
                self.assertTrue(set(names) <= set(compat.CONSTANTS.get(module, ())), module)

    def test_each_default_source_drift_suspends_apply_recovery_and_off_without_writes(self):
        changes = [(module, name) for module, names in REQUIRED.items() for name in names
                   if not name.startswith('_explicit_')]
        changes += [(module, name) for module, names in TABLES.items() for name in names]
        for module, name in changes:
            with self.subTest(symbol=module + '.' + name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                synthetic_sources(root)
                specs = {m: tuple(n for n in compat.FUNCTIONS.get(m, ()) if n in names) for m, names in REQUIRED.items()}
                const_specs = {m: compat.CONSTANTS[m] for m in
                               ('hermes_cli.auth_constants', RUNTIME, 'hermes_cli.providers')}
                if SWITCH in compat.CONSTANTS:
                    const_specs[SWITCH] = compat.CONSTANTS[SWITCH]
                expected = compat.collect_symbols(root, specs=specs, constant_specs=const_specs)
                revision = 'a' * 40
                data = root / 'qualified.json'
                data.write_text(json.dumps({'hosts': [dict(expected, revision=revision, label='synthetic')]}))
                backend_module = types.ModuleType('hermes_cli.config_backend')
                backend_module.__file__ = str(root / 'hermes_cli/config_backend.py')
                constants_module = types.ModuleType('hermes_constants')
                constants_module.get_hermes_home = lambda: root
                def collect(*args, **kwargs):
                    return original_collect(root, specs=specs, constant_specs=const_specs)
                original_collect = compat.collect_symbols
                with mock.patch.dict(sys.modules, {'hermes_cli.config_backend': backend_module,
                                                    'hermes_constants': constants_module}), \
                     mock.patch.object(compat, 'DATA', data), mock.patch.object(compat, 'FUNCTIONS', specs), \
                     mock.patch.object(compat, 'CONSTANTS', const_specs), \
                     mock.patch.object(compat, 'native_revision', return_value=revision), \
                     mock.patch.object(compat, 'collect_symbols', side_effect=collect):
                    self.assertTrue(compat._source_compatibility()['ok'], 'valid inert control')
                    backend = Backend()
                    engine = Engine(root / 'records', backend, compat._source_compatibility)
                    engine.cycle({'conversation': TARGET}, 100)
                    self.assertGreater(len(backend.writes), 0)
                    entry = engine.state['groups']['conversation']
                    durable(root / 'records/journal.json', {'group': 'conversation', 'prior': entry['baseline'],
                            'target': entry['last'], 'at': 100})
                    backend.document['model']['default'] = entry['baseline']['model.default']['value']
                    before, writes = backend.read(), copy.deepcopy(backend.writes)
                    files = {p.name: p.read_bytes() for p in (root / 'records').iterdir()}
                    path = root.joinpath(*module.split('.')).with_suffix('.py')
                    source = path.read_text()
                    if name in TABLES.get(module, ()):
                        if name == '_PROVIDER_API_MODE_OVERRIDES':
                            source = source.replace('("nous",)', '("nous", "openai-codex")')
                        elif name == '_POOL_ENTRY_SIMPLE_MODES':
                            source = source.replace('("codex_responses", DEFAULT_CODEX_BASE_URL)',
                                                    '("changed_mode", DEFAULT_CODEX_BASE_URL)')
                        else:
                            source = source.replace('runtime_credentials(), "codex_responses"',
                                                    'runtime_credentials(), "changed_mode"')
                    elif name == '_OAuthRuntimeSpec':
                        source = source.replace('class _OAuthRuntimeSpec:\n    pass', 'class _OAuthRuntimeSpec:\n    changed = True')
                    else:
                        marker = ('def ' + name.split('.')[-1] + '(')
                        start = source.index(marker)
                        offset = source.index('"baseline"', start)
                        source = source[:offset] + source[offset:].replace('"baseline"', '"changed"', 1)
                    self.assertNotEqual(source, path.read_text(), 'negative control must change the source')
                    path.write_text(source)
                    result = compat._source_compatibility()
                    self.assertFalse(result['ok'], result)
                    self.assertIn(module + '.' + name, result['reasons'])
                    engine.cycle({'conversation': dict(TARGET, provider='openai-codex', model='gpt-6.1-sol')}, 200)
                    self.assertFalse(engine.recover())
                    self.assertFalse(engine.restore(300))
                    self.assertEqual(backend.read(), before)
                    self.assertEqual(backend.writes, writes)
                    self.assertEqual({p.name: p.read_bytes() for p in (root / 'records').iterdir()}, files)

    def test_table_inspection_never_executes_constructors_lambdas_or_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            synthetic_sources(root)
            with mock.patch('builtins.__import__', side_effect=AssertionError('no native import')):
                found = compat.collect_symbols(root, specs={}, constant_specs=TABLES)
            self.assertTrue(all(value is not None for value in found['constants'].values()), found)
            oauth = found['constants'][RUNTIME + '._OAUTH_RUNTIME_PROVIDERS']
            self.assertEqual(oauth['routes']['openai-codex']['api_mode'], 'codex_responses')
