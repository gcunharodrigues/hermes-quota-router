"""HQR-38 safety net fingerprints: native code that reads and acts on `fallback_providers` (decisions/hqr-38-spec.md, D-28/D-29).

The plugin writes the chain and relies on native normalization, refresh, activation, primary restore and delegation inheritance.
Drift in any of them must suspend Auto by name; a host measured before HQR-38 must fail closed until requalified.
"""
import copy
import json
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat

REVISION = '3b421578588243f920886e6fe79a6faa87ea026e'
# Contract of this slice: the minimal native set the safety net design depends on (decisions/hqr-38-delivery.md).
SAFETY_NET = {
    'hermes_cli.fallback_config': ('_normalized_base_url', '_iter_fallback_entries', '_entry_identity',
                                   'get_fallback_chain', 'scoped_fallback_chain'),
    'gateway.run_config_loaders': ('GatewayConfigLoadersMixin._refresh_fallback_model',
                                   'GatewayConfigLoadersMixin._apply_fallback_chain_to_agent'),
    'tui_gateway.agent_callbacks': ('_sync_agent_fallback_with_config',),
    'hermes_cli.cli_chat_turn_mixin': ('CLIChatTurnMixin._sync_fallback_chain_with_config',),
    'cron.scheduler': ('_job_fallback_chain',),
    'agent.agent_init_fallback': ('_fallback_entries', '_init_fallback_chain'),
    'agent.chat_completion_helpers': ('try_activate_fallback',),
    'agent.agent_runtime_helpers': ('restore_primary_runtime',),
    'tools.delegate_tool_routes': ('_with_inherited_fallback', '_route_to_task_route'),
    'tools.delegate_tool_config': ('_resolve_child_fallback_chain', '_resolve_child_runtime'),
}
KEYS = {module + '.' + name for module, names in SAFETY_NET.items() for name in names}

SOURCES = {
    'hermes_cli/fallback_config.py': '''
def get_fallback_chain(config):
    return list((config or {}).get("fallback_providers") or [])


def scoped_fallback_chain(inherited, declared, *, pinned, owner):
    return None if declared == [] else declared or (None if pinned else inherited)
''',
    'gateway/run_config_loaders.py': '''
class GatewayConfigLoadersMixin:
    @staticmethod
    def _apply_fallback_chain_to_agent(agent, chain):
        agent._fallback_chain = list(chain or [])
''',
    'tools/delegate_tool_routes.py': '''
def _with_inherited_fallback(route, config):
    if route.get("profile") or route.get("fallback_providers") is not None:
        return route
    inherited = config.get("fallback_providers")
    return route if inherited is None else {**route, "fallback_providers": inherited}
''',
}
DRIFT = {
    'hermes_cli.fallback_config.get_fallback_chain': ('hermes_cli/fallback_config.py', '"fallback_providers"', '"fallback_model"'),
    'gateway.run_config_loaders.GatewayConfigLoadersMixin._apply_fallback_chain_to_agent':
        ('gateway/run_config_loaders.py', 'list(chain or [])', 'list(chain or [])[:1]'),
    'tools.delegate_tool_routes._with_inherited_fallback':
        ('tools/delegate_tool_routes.py', 'is not None', 'is not None and route.get("fallback_providers") != []'),
}


def hosts():
    return json.loads(compat.DATA.read_text(encoding='utf-8'))['hosts']


def docker():
    return [entry for entry in hosts() if entry['label'].startswith('Docker hqr-s1-test;')][0]


class SafetyNetSetTests(unittest.TestCase):
    def test_compat_requires_every_safety_net_symbol(self):
        self.assertEqual(compat.SAFETY_NET, SAFETY_NET)
        for module, names in SAFETY_NET.items():
            for name in names:
                with self.subTest(symbol=module + '.' + name):
                    self.assertIn(name, compat.FUNCTIONS.get(module, ()))

    def test_changed_fallback_source_changes_only_its_own_fingerprint(self):
        # Only names the compat set requires are collected, so a missing requirement fails here.
        specs = {module: tuple(n for n in compat.FUNCTIONS.get(module, ()) if module + '.' + n in DRIFT)
                 for module in ('hermes_cli.fallback_config', 'gateway.run_config_loaders', 'tools.delegate_tool_routes')}
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules):
            root = Path(directory)
            for module in specs:
                sys.modules.pop(module, None)
            for relative, text in SOURCES.items():
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_text(text, encoding='utf-8')
            baseline = compat.collect_symbols(root, specs=specs, constant_specs={})['functions']
            self.assertEqual(set(baseline), set(DRIFT))
            self.assertTrue(all(re.fullmatch('[0-9a-f]{64}', value or '') for value in baseline.values()), baseline)
            for key, (relative, old, new) in DRIFT.items():
                with self.subTest(symbol=key):
                    path = root / relative
                    original = path.read_text(encoding='utf-8')
                    path.write_text(original.replace(old, new, 1), encoding='utf-8')
                    changed = compat.collect_symbols(root, specs=specs, constant_specs={})['functions']
                    path.write_text(original, encoding='utf-8')
                    self.assertEqual({k for k in baseline if baseline[k] != changed[k]}, {key})


class QualificationTests(unittest.TestCase):
    def check(self, entries, symbols, *, revision=REVISION):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            if revision is not None:
                (root / '.git').mkdir()
                (root / '.git/HEAD').write_text(revision + '\n')
            data = root / 'hosts.json'
            data.write_text(json.dumps({'hosts': entries}))
            backend = types.ModuleType('hermes_cli.config_backend')
            backend.__file__ = str(root / 'hermes_cli/config_backend.py')
            constants = types.ModuleType('hermes_constants')
            constants.get_hermes_home = lambda: root / 'synthetic-home'
            with mock.patch.dict(sys.modules, {'hermes_cli.config_backend': backend, 'hermes_constants': constants}), \
                    mock.patch.object(compat, 'DATA', data), \
                    mock.patch.object(compat, 'collect_symbols', return_value=symbols), \
                    mock.patch.dict('os.environ', {'HERMES_CONFIG_BACKEND': 'file'}):
                return compat._source_compatibility()

    def test_working_entry_binds_every_safety_net_symbol(self):
        working = hosts()[0]
        self.assertEqual(working['revision'], REVISION)
        self.assertNotIn('requalification_required', working)
        for key in sorted(KEYS):
            with self.subTest(symbol=key):
                self.assertRegex(working['functions'].get(key) or '', '^[0-9a-f]{64}$')

    def test_changed_safety_net_function_is_reported_by_name(self):
        working = hosts()[0]
        symbols = {kind: copy.deepcopy(working[kind]) for kind in ('functions', 'constants')}
        self.assertTrue(self.check([working], symbols)['ok'])
        for key in sorted(KEYS):
            with self.subTest(symbol=key):
                original = symbols['functions'][key]
                symbols['functions'][key] = '0' * 64
                result = self.check([working], symbols)
                symbols['functions'][key] = original
                self.assertFalse(result['ok'])
                self.assertEqual(result['reasons'], [key])

    def test_docker_entry_is_not_fabricated_and_fails_closed_until_requalified(self):
        entry = docker()
        self.assertNotIn('requalification_required', entry)
        self.assertTrue(KEYS <= set(entry['functions']), 'Docker hashes must come from the measured Docker target')
        # Even a complete matching set cannot select an entry that still awaits requalification.
        complete = copy.deepcopy(entry)
        complete['requalification_required'] = 'Synthetic pending inspection; matching source is not sufficient'
        symbols = {kind: copy.deepcopy(complete[kind]) for kind in ('functions', 'constants')}
        for revision in (REVISION, None):
            with self.subTest(revision=revision):
                result = self.check([complete], symbols, revision=revision)
                self.assertFalse(result['ok'])
                self.assertEqual(result['reasons'], ['host_requalification_required'])
        del complete['requalification_required']
        self.assertTrue(self.check([complete], symbols, revision=None)['ok'])


if __name__ == '__main__':
    unittest.main()
