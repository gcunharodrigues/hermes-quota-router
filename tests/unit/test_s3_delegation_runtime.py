"""The active registration and readable status must not borrow an unrelated plugin's evidence."""
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router.compat import collect_symbols
from quota_router.render import render


class RuntimeEvidenceTests(unittest.TestCase):
    def test_active_scoped_plugin_cannot_borrow_a_pristine_bare_module(self):
        name = 'hermes_plugins.advanced_delegation.model_map'
        scoped = 'hermes_plugins.advanced_delegation__home_synthetic.model_map'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'model_map.py'
            source = 'class ModelMapDelegationProvider:\n    def route_task(self):\n        return {}\n'
            path.write_text(source)
            bare = types.ModuleType(name)
            exec(compile(source, str(path), 'exec'), bare.__dict__)
            loaded = types.ModuleType(scoped)
            exec(compile(source, str(path), 'exec'), loaded.__dict__)
            loaded.ModelMapDelegationProvider.route_task = len
            active = loaded.ModelMapDelegationProvider()
            registry = types.ModuleType('agent.delegation_registry')
            registry._registry = types.SimpleNamespace(get_provider=lambda _: active)
            with mock.patch.dict(sys.modules, {name: bare, scoped: loaded, 'agent.delegation_registry': registry}):
                found = collect_symbols(root, specs={name: ('ModelMapDelegationProvider.route_task',)},
                                        constant_specs={}, plugin_root=root)
            self.assertIsNone(found['functions'][name + '.ModelMapDelegationProvider.route_task'])

    def test_human_status_names_unavailable_dependency_even_in_observe(self):
        payload = {'mode_effective': 'observe', 'subagents': {'ok': False, 'reason': 'advanced_delegation_unavailable'}}
        text = render('status', payload)
        self.assertIn('advanced-delegation', text)
        self.assertIn('indispon', text.lower())


if __name__ == '__main__':
    unittest.main()
