"""Desempenho 2026-11-18: the profile document is parsed again exactly when its bytes change, never shared mutably."""
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat, compat_tables, inventory, mapping
from quota_router.groups import aliased


def host(calls):
    def read_config_doc(path):
        calls.append(Path(path).read_text(encoding='utf-8'))
        return {'model': {'default': calls[-1].strip()}, 'list': [1, 2]}

    backend = types.ModuleType('hermes_cli.config_backend')
    backend.read_config_doc = read_config_doc
    return {'hermes_cli': types.ModuleType('hermes_cli'), 'hermes_cli.config_backend': backend}


class DocumentCacheTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.path = Path(self.root.name) / 'config.yaml'
        self.path.write_text('a\n', encoding='utf-8')
        self.calls = []
        patcher = mock.patch.dict('sys.modules', host(self.calls))
        patcher.start()
        self.addCleanup(patcher.stop)
        inventory._DOCUMENTS.clear()
        self.addCleanup(inventory._DOCUMENTS.clear)

    def test_same_bytes_reuse_a_private_copy_and_new_bytes_parse_again(self):
        first = inventory.read_document(self.path)
        first['model']['default'] = 'mutated'
        first['list'].append(3)
        second = inventory.read_document(self.path)
        self.assertEqual(second, {'model': {'default': 'a'}, 'list': [1, 2]})
        self.assertEqual(len(self.calls), 1)
        self.path.write_text('b\n', encoding='utf-8')
        self.assertEqual(inventory.read_document(self.path)['model']['default'], 'b')
        self.assertEqual(len(self.calls), 2)

    def test_another_reader_or_backend_is_never_served_from_the_cache(self):
        inventory.read_document(self.path)
        with mock.patch.dict('sys.modules', host(self.calls)):
            inventory.read_document(self.path)
        self.assertEqual(len(self.calls), 2)
        with mock.patch.dict(os.environ, {'HERMES_CONFIG_BACKEND': 'remote'}):
            inventory.read_document(self.path)
            inventory.read_document(self.path)
        self.assertEqual(len(self.calls), 4)

    def test_unreadable_file_uses_the_native_reader_and_its_error(self):
        self.path.unlink()
        with self.assertRaises(FileNotFoundError):
            inventory.read_document(self.path)


class CatalogFileTests(unittest.TestCase):
    def test_models_dev_file_is_parsed_again_only_when_it_changes(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'models_dev_cache.json'
            module = types.ModuleType('agent.models_dev')
            module._models_dev_cache, module._get_cache_path = {}, lambda: path
            module.PROVIDER_TO_MODELS_DEV = {'anthropic': 'anthropic', 'openai-codex': 'openai'}
            path.write_text('{"anthropic": {"models": {"claude-opus-5-5": {}}}}', encoding='utf-8')
            with mock.patch.dict('sys.modules', {'agent.models_dev': module}), \
                    mock.patch.object(mapping.json, 'load', wraps=mapping.json.load) as load:
                self.assertEqual(mapping.native_catalogs(), {'anthropic': ['claude-opus-5-5']})
                self.assertEqual(mapping.native_catalogs(), {'anthropic': ['claude-opus-5-5']})
                self.assertEqual(load.call_count, 1)
                path.write_text('{"openai": {"models": {"gpt-6.2-sol": {}, "gpt-6-luna": {}}}}', encoding='utf-8')
                self.assertEqual(mapping.native_catalogs(), {'openai-codex': ['gpt-6.2-sol', 'gpt-6-luna']})
                self.assertEqual(load.call_count, 2)
                path.unlink()
                self.assertEqual(mapping.native_catalogs(), {})


class AliasTests(unittest.TestCase):
    def test_alias_or_cycle_on_a_leaf_path_is_found_and_elsewhere_ignored(self):
        shared = {'x': 1}
        self.assertTrue(aliased({'a': shared, 'b': shared}, [('a', 'x')]))
        self.assertFalse(aliased({'a': shared, 'b': shared}, [('c', 'x')]))
        cycle = {'a': {}}
        cycle['a']['back'] = cycle
        self.assertTrue(aliased(cycle, [('a', 'z')]))
        self.assertFalse(aliased({'a': shared, 'b': shared}, []))

    def test_counts_kept_for_one_document_answer_each_group_and_a_new_document_is_counted_again(self):
        shared = {'x': 1}
        document = {'a': shared, 'b': shared, 'c': {'y': 2}}
        self.assertTrue(aliased(document, [('a', 'x')]))
        self.assertFalse(aliased(document, [('c', 'y')]))
        self.assertTrue(aliased(document, [('b',)]))
        self.assertFalse(aliased({'a': {'x': 1}, 'b': {'x': 1}}, [('a', 'x')]))


class QualificationCacheTests(unittest.TestCase):
    def loaded(self, path, source):
        path.write_text(source, encoding='utf-8')
        scope = {}
        exec(compile(source, str(path), 'exec'), scope)
        return scope['TABLE']['codex']

    def test_resolver_lambda_shape_follows_the_file_through_the_parse_cache(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'runtime_provider.py'
            first = compat_tables.loaded_lambda(self.loaded(path, "TABLE = {'codex': lambda c: c}\n"), compat._parsed)
            self.assertEqual(compat_tables.loaded_lambda(self.loaded(path, "TABLE = {'codex': lambda c: c}\n"), compat._parsed),
                             first)
            changed = self.loaded(path, "TABLE = {'codex': lambda c, d=1: d}\n")
            self.assertNotEqual(compat_tables.loaded_lambda(changed, compat._parsed), first)
            self.assertEqual(compat_tables.loaded_lambda(changed), compat_tables.loaded_lambda(changed, compat._parsed))

    def test_source_constant_follows_the_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'constants.py'
            path.write_text("A = 'x'\nB = A\n", encoding='utf-8')
            self.assertEqual(compat.source_constant(path, 'B'), 'x')
            path.write_text("A = 'yy'\nB = A\n", encoding='utf-8')
            self.assertEqual(compat.source_constant(path, 'B'), 'yy')


if __name__ == '__main__':
    unittest.main()
