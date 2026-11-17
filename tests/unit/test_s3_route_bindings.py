# Regression contract: decisions/hqr-20-amendment.md, D18/R1: active table drift and inert reexports.
import copy
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat, routes
from test_s3_default_resolution import RUNTIME, SWITCH, TABLES, synthetic_sources


class RouteBindingTests(unittest.TestCase):
    def test_inert_reexport_follows_the_builder_without_importing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'entry.py').write_text('from builders import build as select\n')
            (root / 'builders.py').write_text('raise RuntimeError("never import")\ndef build():\n    return "baseline"\n')
            with mock.patch('builtins.__import__', side_effect=AssertionError('no imports')):
                found = compat.collect_symbols(root, specs={'entry': ('select',)}, constant_specs={})
            self.assertIsNotNone(found['functions']['entry.select'])
            (root / 'builders.py').write_text('raise RuntimeError("never import")\ndef build():\n    return "changed"\n')
            changed = compat.collect_symbols(root, specs={'entry': ('select',)}, constant_specs={})
            self.assertNotEqual(found, changed)

    def test_live_route_tables_cannot_borrow_pristine_disk_bindings(self):
        for name, change in [('_OAUTH_RUNTIME_PROVIDERS', 'mode'), ('_OAUTH_RUNTIME_PROVIDERS', 'resolver'),
                             ('_POOL_ENTRY_SIMPLE_MODES', 'mode'), ('_POOL_ENTRY_SIMPLE_MODES', 'url'),
                             ('_PROVIDER_API_MODE_OVERRIDES', 'provider')]:
            with self.subTest(name=name, change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                synthetic_sources(root)
                runtime, switch = types.ModuleType(RUNTIME), types.ModuleType(SWITCH)
                resolve = lambda: resolve_codex_runtime_credentials()
                runtime.__dict__['_OAUTH_RUNTIME_PROVIDERS'] = {'openai-codex': types.SimpleNamespace(
                    api_mode='codex_responses', default_base_url='', resolve=resolve)}
                runtime.__dict__['_POOL_ENTRY_SIMPLE_MODES'] = {'openai-codex': (
                    'codex_responses', 'https://chatgpt.com/backend-api/codex')}
                switch.__dict__['_PROVIDER_API_MODE_OVERRIDES'] = {'nous': resolve}
                inert = compat.collect_symbols(root, specs={}, constant_specs=TABLES)
                with mock.patch.dict(sys.modules, {RUNTIME: runtime, SWITCH: switch}):
                    live = compat.collect_symbols(root, specs={}, constant_specs=TABLES)
                    self.assertEqual(live, inert, 'valid loaded control')
                    if name == '_OAUTH_RUNTIME_PROVIDERS':
                        spec = runtime.__dict__[name]['openai-codex']
                        if change == 'mode':
                            spec.api_mode = 'changed_mode'
                        else:
                            spec.resolve = lambda: forbidden()
                    elif name == '_POOL_ENTRY_SIMPLE_MODES':
                        old = runtime.__dict__[name]['openai-codex']
                        runtime.__dict__[name]['openai-codex'] = ('changed_mode', old[1]) if change == 'mode' else (old[0], 'changed_url')
                    else:
                        switch.__dict__[name]['openai-codex'] = resolve
                    changed = compat.collect_symbols(root, specs={}, constant_specs=TABLES)
                module = SWITCH if name == '_PROVIDER_API_MODE_OVERRIDES' else RUNTIME
                self.assertIsNone(changed['constants'][module + '.' + name])

    def test_requalified_dispatch_modes_must_still_match_the_public_mirror(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            synthetic_sources(root)
            specs = {module: compat.CONSTANTS[module] for module in ('hermes_cli.auth_constants', RUNTIME, 'hermes_cli.providers')}
            specs[SWITCH] = TABLES[SWITCH]
            constants = compat.collect_symbols(root, specs={}, constant_specs=specs)['constants']
            self.assertTrue(routes.mirror_matches(constants))
            for name in ('_OAUTH_RUNTIME_PROVIDERS', '_POOL_ENTRY_SIMPLE_MODES'):
                changed = copy.deepcopy(constants)
                changed[RUNTIME + '.' + name]['routes']['openai-codex']['api_mode'] = 'changed_mode'
                self.assertFalse(routes.mirror_matches(changed), name)
