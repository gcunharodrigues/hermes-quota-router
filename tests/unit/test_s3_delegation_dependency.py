"""Runtime registration, not saved options, admits native subagent writes."""
import copy
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat
from quota_router.apply import Engine
from s3_fakes import Backend, TARGET, qualified
import test_s3_lifecycle as fixtures


class DependencyTests(unittest.TestCase):
    def test_native_status_requires_enabled_loaded_model_map_without_discovery(self):
        self.assertTrue(hasattr(compat, 'native_delegation_status'), 'runtime dependency check missing')
        cfg = {'delegation': {'backend': 'model_map'}, 'plugins': {'enabled': ['advanced-delegation'], 'disabled': []}}
        provider = types.SimpleNamespace(is_available=lambda: True)
        registry = types.SimpleNamespace(get_provider=lambda name: provider if name == 'model_map' else None)
        module = types.ModuleType('agent.delegation_registry')
        module._registry = registry
        module.get_active_provider = lambda *_: self.fail('must not discover or bootstrap plugins')
        with mock.patch.dict(sys.modules, {'agent.delegation_registry': module}):
            self.assertTrue(compat.native_delegation_status(cfg)['ok'])
            for mutation in ('disabled', 'not_enabled', 'wrong_backend', 'not_loaded', 'unavailable'):
                bad = copy.deepcopy(cfg)
                module._registry = registry
                provider.is_available = lambda: True
                if mutation == 'disabled':
                    bad['plugins']['disabled'] = ['advanced-delegation']
                elif mutation == 'not_enabled':
                    bad['plugins']['enabled'] = []
                elif mutation == 'wrong_backend':
                    bad['delegation']['backend'] = 'default'
                elif mutation == 'not_loaded':
                    module._registry = types.SimpleNamespace(get_provider=lambda _: None)
                else:
                    provider.is_available = lambda: False
                with self.subTest(mutation=mutation):
                    self.assertFalse(compat.native_delegation_status(bad)['ok'])

    def test_missing_runtime_dependency_never_writes_routes_including_off_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = Backend()
            state = {'ok': True}
            compatibility = lambda: dict(qualified(), subagents=dict(state))
            engine = Engine(directory, backend, compatibility)
            engine.cycle({'general': TARGET}, now=100)
            self.assertTrue(backend.writes)
            state['ok'] = False
            before, count = backend.read(), len(backend.writes)
            engine.cycle({'general': {**TARGET, 'effort': 'low'}}, now=200)
            engine.restore(now=300)
            self.assertEqual(backend.read(), before)
            self.assertEqual(len(backend.writes), count)
            self.assertIn('general', engine.report(300)['groups_out'])

    def test_status_reports_unavailable_route_and_preserves_conversation(self):
        fixture = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as directory:
            m, ctx, backend = fixture.manager(Path(directory), compatible=lambda: dict(qualified(), subagents={'ok': False}))
            self.addCleanup(m.close)
            before = copy.deepcopy(backend.document['delegation'])
            fixture.call(m, 'config approve-map base')
            status = fixture.call(m, 'mode auto')
            self.assertEqual(status['decisions']['routes']['general']['state'], 'backend_unavailable')
            self.assertFalse(status['subagents']['ok'])
            self.assertEqual(backend.document['delegation'], before)
            self.assertEqual(backend.document['model']['provider'], 'anthropic')

    def test_fingerprint_specs_include_native_backend_and_external_route_resolution(self):
        self.assertIn('hermes_plugins.advanced_delegation.model_map', compat.FUNCTIONS)
        names = compat.FUNCTIONS['hermes_plugins.advanced_delegation.model_map']
        for name in ('configured_options', '_entry_problem', '_text', 'ModelMapDelegationProvider.task_parameters',
                     'ModelMapDelegationProvider.route_task'):
            self.assertIn(name, names)
        self.assertIn('tools.delegate_tool_routes', compat.FUNCTIONS)
        with tempfile.TemporaryDirectory() as root:
            plugin = Path(root) / 'plugin'
            plugin.mkdir()
            (plugin / 'model_map.py').write_text('def route_task():\n    return {}\n')
            found = compat.collect_symbols(root, specs={'hermes_plugins.advanced_delegation.model_map': ('route_task',)},
                                           constant_specs={}, plugin_root=plugin)
            self.assertIsNotNone(found['functions']['hermes_plugins.advanced_delegation.model_map.route_task'])


if __name__ == '__main__':
    unittest.main()
