"""Native-shaped catalog/effort edge contracts and complete Auto diagnostics."""
import copy
import json
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router.inventory import cron_origins
from quota_router.mapping import approved_base, native_catalogs
from s3_fakes import Backend, TARGET, qualified
import test_s3_lifecycle as lifecycle_tests


class EdgeTests(unittest.TestCase):
    def models_dev(self):
        module = types.ModuleType('agent.models_dev')
        module.PROVIDER_TO_MODELS_DEV = {'anthropic': 'anthropic', 'openai-codex': 'openai'}
        module._models_dev_cache = {'openai': {'models': {}}, 'anthropic': {'models': {}}}
        for pair in approved_base().values():
            for provider in module.PROVIDER_TO_MODELS_DEV:
                if provider in pair:
                    module._models_dev_cache[module.PROVIDER_TO_MODELS_DEV[provider]]['models'][pair[provider]['model']] = {}
        module.fetch_models_dev = mock.Mock(side_effect=AssertionError('Loaded memory must not perform I/O'))
        return module

    def test_loaded_models_dev_memory_overrides_curated_floor_without_io(self):
        module = self.models_dev()
        curated = types.ModuleType('hermes_cli.models_catalog_static')
        curated._PROVIDER_MODELS = {'anthropic': ['claude-opus-5-5'], 'openai-codex': ['gpt-6.1-sol']}
        with mock.patch.dict(sys.modules, {'agent.models_dev': module, 'hermes_cli.models_catalog_static': curated}):
            catalogs = native_catalogs()
        self.assertEqual(catalogs, {'anthropic': ['claude-opus-5-5', 'claude-sonnet-5-5', 'claude-haiku-5-5'],
                                    'openai-codex': ['gpt-6.1-sol', 'gpt-6.1-terra', 'gpt-6-luna']})
        module.fetch_models_dev.assert_not_called()

    def test_models_dev_present_ids_route_routine_triage_extract_despite_curated_floor(self):
        helper = lifecycle_tests.AutoCommandTests()
        module = self.models_dev()
        curated = types.ModuleType('hermes_cli.models_catalog_static')
        curated._PROVIDER_MODELS = {'anthropic': ['claude-opus-5-5'], 'openai-codex': ['gpt-6.1-sol']}
        with mock.patch.dict(sys.modules, {'agent.models_dev': module, 'hermes_cli.models_catalog_static': curated}), \
                tempfile.TemporaryDirectory() as root:
            m, ctx, backend = helper.manager(root)
            self.addCleanup(m.close)
            options = backend.document['delegation']['backends']['model_map']['options']
            options[:] = [dict(name=role, provider='openai-codex', model='gpt-6.1-sol', reasoning_effort='medium')
                          for role in ('routine', 'triage', 'extract')]
            helper.call(m, 'config approve-map base')
            result = helper.call(m, 'mode auto')
            for row in options:
                self.assertEqual(result['decisions']['routes'][row['name']]['state'], 'decided')
            applied = backend.read()['delegation']['backends']['model_map']['options']
            self.assertEqual([(row['provider'], row['model']) for row in applied],
                             [('anthropic', 'claude-sonnet-5-5'), ('anthropic', 'claude-sonnet-5-5'),
                              ('anthropic', 'claude-haiku-5-5')])
            module.fetch_models_dev.assert_not_called()

    def test_models_dev_offline_reader_is_used_when_memory_is_empty(self):
        module = self.models_dev()
        registry = module._models_dev_cache
        module._models_dev_cache = {}
        module.fetch_models_dev = mock.Mock(return_value=registry)
        with tempfile.TemporaryDirectory() as root:
            from pathlib import Path
            cache = Path(root) / 'catalog.json'
            cache.write_text(json.dumps(registry))
            module._get_cache_path = lambda: cache
            with mock.patch.dict(sys.modules, {'agent.models_dev': module}):
                self.assertIn('gpt-6.1-terra', native_catalogs().get('openai-codex', []))
        module.fetch_models_dev.assert_not_called()

    def test_models_dev_module_is_loaded_only_when_not_already_loaded(self):
        module = self.models_dev()
        registry = module._models_dev_cache
        module._models_dev_cache = {}
        module.fetch_models_dev = mock.Mock(return_value=registry)
        with tempfile.TemporaryDirectory() as root:
            from pathlib import Path
            cache = Path(root) / 'catalog.json'
            cache.write_text(json.dumps(registry))
            module._get_cache_path = lambda: cache
            with mock.patch.dict(sys.modules, {'agent.models_dev': None}), \
                    mock.patch('importlib.import_module', return_value=module) as loader:
                self.assertIn('claude-haiku-5-5', native_catalogs().get('anthropic', []))
        loader.assert_called_once_with('agent.models_dev')
        module.fetch_models_dev.assert_not_called()

    def test_models_dev_provider_mapping_is_owned_by_host(self):
        module = self.models_dev()
        module._models_dev_cache['host-openai'] = module._models_dev_cache.pop('openai')
        module.PROVIDER_TO_MODELS_DEV['openai-codex'] = 'host-openai'
        with mock.patch.dict(sys.modules, {'agent.models_dev': module}):
            self.assertIn('gpt-6.1-terra', native_catalogs().get('openai-codex', []))
        module.fetch_models_dev.assert_not_called()

    def test_models_dev_unavailable_empty_or_malformed_is_unknown_not_curated_floor(self):
        curated = types.ModuleType('hermes_cli.models_catalog_static')
        curated._PROVIDER_MODELS = {'anthropic': [], 'openai-codex': []}
        for registry in ({}, None, [], {'anthropic': {'models': {}}}, {'openai': {'models': []}},
                         {'anthropic': {'models': {4: {}}}}, {'anthropic': 'invalid'}):
            with self.subTest(registry=registry):
                module = self.models_dev()
                module._models_dev_cache = registry
                module.fetch_models_dev = mock.Mock(return_value=registry)
                with mock.patch.dict(sys.modules, {'agent.models_dev': module, 'hermes_cli.models_catalog_static': curated}):
                    self.assertEqual(native_catalogs(), {})
        module = self.models_dev()
        module._models_dev_cache = {}
        module.fetch_models_dev = mock.Mock(side_effect=OSError('SYNTHETIC_PRIVATE_ERROR'))
        with mock.patch.dict(sys.modules, {'agent.models_dev': module}):
            self.assertEqual(native_catalogs(), {})

    def test_unknown_models_dev_routes_with_visible_status_note(self):
        helper = lifecycle_tests.AutoCommandTests()
        for registry in ({}, {'anthropic': {'models': {}}, 'openai': {'models': {}}},
                         {'openai': {'models': {'gpt-6.1-sol': {}}}}):
            with self.subTest(registry=registry), tempfile.TemporaryDirectory() as root:
                module = self.models_dev()
                module._models_dev_cache = registry
                module.fetch_models_dev = mock.Mock(return_value=registry)
                with mock.patch.dict(sys.modules, {'agent.models_dev': module}):
                    m, ctx, backend = helper.manager(root)
                    try:
                        helper.call(m, 'config approve-map base')
                        result = helper.call(m, 'mode auto')
                        decision = result['decisions']['conversation']
                        self.assertEqual(decision['state'], 'decided')
                        self.assertEqual(backend.document['model']['provider'], 'anthropic')
                        self.assertEqual(decision.get('catalog_note'), 'IDs não verificados')
                        self.assertIn('anthropic', decision['catalog_unverified'])
                        for command in ('status', 'explain'):
                            self.assertIn('IDs não verificados', m.command(command))
                            self.assertEqual(helper.call(m, command)['decisions']['conversation']['catalog_note'],
                                             'IDs não verificados')
                    finally:
                        m.close()

    def test_readable_models_dev_absence_is_named_in_status_text(self):
        helper = lifecycle_tests.AutoCommandTests()
        module = self.models_dev()
        del module._models_dev_cache['anthropic']['models']['claude-opus-5-5']
        with mock.patch.dict(sys.modules, {'agent.models_dev': module}), tempfile.TemporaryDirectory() as root:
            m, ctx, backend = helper.manager(root)
            try:
                helper.call(m, 'config approve-map base')
                helper.call(m, 'mode auto')
                status = helper.call(m, 'status')
                self.assertEqual(status['decisions']['conversation'].get('catalog_missing'), ['anthropic'])
                self.assertIn('ID ausente do catálogo models.dev', m.command('status'))
                self.assertNotIn('IDs não verificados', m.command('status'))
                self.assertEqual(backend.writes, [])
            finally:
                m.close()

    def test_native_models_dev_reader_and_offline_dependencies_are_fingerprinted(self):
        from quota_router import compat
        expected = {'fetch_models_dev', '_load_disk_cache', '_validate_registry', '_get_cache_path', '_hermes_path',
                    '_quarantine_corrupt_cache', '_clear_etag', '_quietly', '_disk_cache_age_seconds'}
        self.assertTrue(expected <= set(compat.FUNCTIONS.get('agent.models_dev', ())))
        self.assertIn('PROVIDER_TO_MODELS_DEV', compat.CONSTANTS.get('agent.models_dev', ()))

    def test_cron_effort_native_false_dict_and_alias_forms(self):
        backend = Backend()
        cfg = backend.document
        cfg['cron']['model'] = 'gpt-6.1-terra'
        cfg['agent']['reasoning_overrides'] = {'openai/gpt-6-1-terra': {'enabled': True, 'effort': 'low'}}
        rows = cron_origins(cfg, [{'id': 'false-pin', 'reasoning_effort': False},
                                  {'id': 'dict-pin', 'reasoning_effort': {'enabled': True, 'effort': 'xhigh'}},
                                  {'id': 'none-pin', 'reasoning_effort': 'disabled'}])
        self.assertEqual(rows['default']['effort'], {'value': 'low', 'origin': 'agent.reasoning_overrides'})
        self.assertEqual([r['effort'] for r in rows['jobs']], [{'value': 'none', 'origin': 'job'},
                         {'value': 'xhigh', 'origin': 'job'}, {'value': 'none', 'origin': 'job'}])

    def test_catalog_absent_disables_entire_role_not_substitute_provider(self):
        helper = lifecycle_tests.AutoCommandTests()
        module = self.models_dev()
        del module._models_dev_cache['anthropic']['models']['claude-opus-5-5']
        with mock.patch.dict(sys.modules, {'agent.models_dev': module}), tempfile.TemporaryDirectory() as root:
            m, ctx, backend = helper.manager(root)
            self.addCleanup(m.close)
            helper.call(m, 'config approve-map base')
            result = helper.call(m, 'mode auto')
            self.assertEqual(backend.writes, [])
            self.assertEqual(result['decisions']['conversation']['state'], 'catalog_model_absent')
            self.assertEqual(result['decisions']['conversation']['reason'], 'model_absent_from_catalog')
            module.fetch_models_dev.assert_not_called()

    def test_suspended_restoration_does_not_claim_off_or_erase_marker(self):
        helper = lifecycle_tests.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = helper.manager(root)
            helper.call(m, 'config approve-map base')
            helper.call(m, 'mode auto')
            before = backend.read()
            m.compatible = lambda: {'ok': False, 'reasons': ['host.changed']}
            result = helper.call(m, 'mode off')
            self.assertFalse(result['ok'])
            self.assertEqual(result['mode_effective'], 'auto')
            self.assertEqual(backend.document, before)
            self.assertIn('host.changed', m.command('status'))
            m.close()


if __name__ == '__main__':
    unittest.main()
