"""No-exec fingerprinting and active-namespace constant drift controls."""
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat
from quota_router.apply import Engine, durable
from s3_fakes import Backend, TARGET, qualified


class FingerprintReviewTests(unittest.TestCase):
    def test_host_binding_uses_revision_and_fingerprints_not_private_location(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'hosts.json'
            defaults = json.loads(compat.DATA.read_text())['hosts'][0]['constants']
            source_specs = {module: compat.CONSTANTS[module] for module in
                            ('hermes_cli.auth_constants', 'hermes_cli.runtime_provider', 'hermes_cli.providers')}
            expected = {'functions': {'native.f': 'digest'}, 'constants': {'native.C': ['x'],
                        **{module + '.' + name: defaults[module + '.' + name] for module, names in source_specs.items() for name in names}}}
            data.write_text(json.dumps({'hosts': [dict(expected, revision='a' * 40, label='synthetic')]}))
            module = types.ModuleType('hermes_cli.config_backend')
            module.__file__ = str(root / 'relocated/hermes_cli/config_backend.py')
            constants = types.ModuleType('hermes_constants')
            constants.get_hermes_home = lambda: root
            with mock.patch.dict(sys.modules, {'hermes_cli.config_backend': module, 'hermes_constants': constants}), \
                    mock.patch.object(compat, 'DATA', data), \
                    mock.patch.object(compat, 'FUNCTIONS', {'native': ('f',)}), \
                    mock.patch.object(compat, 'CONSTANTS', dict(source_specs, native=('C',))), \
                    mock.patch.object(compat, 'collect_symbols', return_value=expected), \
                    mock.patch.object(compat, 'native_revision', return_value='a' * 40, create=True):
                self.assertTrue(compat._source_compatibility()['ok'])
                with mock.patch.object(compat, 'native_revision', return_value='b' * 40):
                    self.assertFalse(compat._source_compatibility()['ok'])

    def test_host_revision_reads_git_metadata_without_spawning_a_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.git/refs/heads').mkdir(parents=True)
            (root / '.git/HEAD').write_text('ref: refs/heads/synthetic\n')
            (root / '.git/refs/heads/synthetic').write_text('a' * 40 + '\n')
            with mock.patch('subprocess.run', side_effect=AssertionError('No product subprocess')):
                self.assertEqual(compat.native_revision(root), 'a' * 40)
                (root / '.git/refs/heads/synthetic').unlink()
                (root / '.git/packed-refs').write_text('b' * 40 + ' refs/heads/synthetic\n')
                self.assertEqual(compat.native_revision(root), 'b' * 40)

    def test_same_name_same_signature_body_drift_blocks_all_write_paths(self):
        import inspect
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            functions = []
            for number in (1, 2):
                path = root / ('body' + str(number) + '.py')
                source = 'def read(value):\n    return value + ' + str(number) + '\n'
                path.write_text(source)
                namespace = {}
                exec(compile(source, str(path), 'exec'), namespace)
                functions.append(namespace['read'])
            self.assertEqual(functions[0].__name__, functions[1].__name__)
            self.assertEqual(inspect.signature(functions[0]), inspect.signature(functions[1]))
            active = {'native.read': functions[0]}
            expected = {'functions': {'native.read': compat.fingerprint(functions[0])}, 'constants': {}}
            backend = Backend()
            engine = Engine(root / 'data', backend, lambda: compat.verify(expected, active, {}))
            engine.cycle({'conversation': TARGET}, 100)
            before, count = backend.read(), len(backend.writes)
            active['native.read'] = functions[1]
            engine.cycle({'conversation': TARGET}, 200)
            self.assertFalse(engine.recover())
            self.assertFalse(engine.restore(300))
            self.assertEqual(backend.read(), before)
            self.assertEqual(len(backend.writes), count)

    def test_external_settings_path_and_validation_constants_are_attested_without_exec(self):
        name = 'hermes_plugins.advanced_delegation.model_map'
        self.assertTrue({'ROUTE_FIELDS', 'BACKEND', 'SETTINGS_PATH', 'PARAMETER', 'DAYBREAK_KEY'} <= set(compat.CONSTANTS[name]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'constants.py'
            path.write_text('BACKEND = "model_map"\nSETTINGS_PATH = f"delegation.backends.{BACKEND}"\n')
            self.assertEqual(compat.source_constant(path, 'SETTINGS_PATH'), 'delegation.backends.model_map')

    def test_inert_inspection_never_executes_default_expression(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'sentinel'
            source = 'def read(value=__import__("pathlib").Path(' + repr(str(marker)) + ').write_text("executed")):\n    return value\n'
            (root / 'inert.py').write_text(source)
            found = compat.collect_symbols(root, specs={'inert': ('read',)}, constant_specs={})
            self.assertFalse(marker.exists(), 'fingerprint executed a default expression')
            self.assertIsNotNone(found['functions']['inert.read'])

    def test_active_scoped_route_constant_drift_suspends_cycle_recovery_and_off(self):
        bare_name = 'hermes_plugins.advanced_delegation.model_map'
        scoped_name = 'hermes_plugins.advanced_delegation__home_review.model_map'
        self.assertIn('ROUTE_FIELDS', compat.CONSTANTS.get(bare_name, ()))
        bare, scoped = types.ModuleType(bare_name), types.ModuleType(scoped_name)
        bare.ROUTE_FIELDS = ('provider', 'model')
        scoped.ROUTE_FIELDS = bare.ROUTE_FIELDS
        provider_type = type('Provider', (), {'__module__': scoped_name})
        registry = types.ModuleType('agent.delegation_registry')
        registry._registry = types.SimpleNamespace(get_provider=lambda _: provider_type())
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules, {
                bare_name: bare, scoped_name: scoped, 'agent.delegation_registry': registry}):
            root = Path(directory)
            def check():
                found = compat.collect_symbols(root, specs={}, constant_specs={bare_name: ('ROUTE_FIELDS',)}, plugin_root=root)
                ok = found['constants'][bare_name + '.ROUTE_FIELDS'] == list(bare.ROUTE_FIELDS)
                return {'ok': ok, 'reasons': [] if ok else [bare_name + '.ROUTE_FIELDS']}
            self.assertTrue(check()['ok'])
            backend = Backend()
            engine = Engine(root, backend, check)
            engine.cycle({'conversation': TARGET}, 100)
            state = engine.state['groups']['conversation']
            durable(root / 'journal.json', {'group': 'conversation', 'prior': state['baseline'], 'target': state['last'], 'at': 100})
            before, count = backend.read(), len(backend.writes)
            scoped.ROUTE_FIELDS = ('model',)
            self.assertFalse(check()['ok'])
            engine.cycle({'conversation': TARGET}, 200)
            self.assertFalse(engine.recover())
            self.assertFalse(engine.restore(300))
            self.assertEqual(backend.read(), before)
            self.assertEqual(len(backend.writes), count)
            self.assertTrue((root / 'journal.json').exists())
