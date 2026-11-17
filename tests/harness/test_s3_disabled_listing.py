"""HQR-32: disabled absence proof must use an untruncated native plugin key."""
import ast
import copy
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class DisabledListingTests(unittest.TestCase):
    def proof(self, *, name='hermes-quota-router', status='disabled', changed=False):
        runner = importlib.import_module('s3_auto')
        assert runner.__file__ is not None
        source = ast.parse(Path(runner.__file__).read_text())
        functions: list[ast.stmt] = [node for node in ast.walk(source) if isinstance(node, ast.FunctionDef) and node.name == 'disabled_proof']
        self.assertEqual(len(functions), 1)
        before = {'plugins': {'enabled': [runner.PLUGIN], 'disabled': [], 'entries': {runner.PLUGIN: {'settings': {'mode': 'auto'}}}},
                  'model': {'default': 'synthetic-model'}}
        after = copy.deepcopy(before)
        after['plugins']['enabled'] = []
        after['plugins']['disabled'] = [runner.PLUGIN]
        if changed:
            after['model']['default'] = 'unexpected-model'
        calls = []
        class Run:
            def json(self, script):
                self_script = script
                if self_script != runner.READ_PROFILE:
                    raise AssertionError('unexpected profile script')
                return after
            def hermes(self, *args):
                calls.append(args)
                if args == ('plugins', 'show', runner.PLUGIN):
                    return SimpleNamespace(stdout='Status: ' + status + '\n')
                if args == ('plugins', 'list', '--plain', '--no-bundled'):
                    return SimpleNamespace(stdout=f'{status} git pinned@aaaaaaaa 0.3.0rc1 {name}\n')
                if args == ('plugins', 'list'):
                    # Rich's fixed-width table truncates this key even when it is installed and disabled.
                    key = 'hermes-quota-r…' if name == runner.PLUGIN else name
                    return SimpleNamespace(stdout=f'│ {key} │ {status} │\n')
                raise AssertionError('unexpected native command: ' + repr(args))
        namespace = {'run': Run(), 'before_disable': before, 'absence_projection': runner.absence_projection,
                     'READ_PROFILE': runner.READ_PROFILE, 'PLUGIN': runner.PLUGIN,
                     'inactive': runner.inactive, 'check': runner.check}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '<installed-disabled-proof>', 'exec'), namespace)
        return namespace['disabled_proof'], calls, runner

    def test_native_disabled_plugin_passes_with_untruncated_plain_listing(self):
        proof, calls, runner = self.proof()
        try:
            result = proof()
        except runner.Failure as error:
            self.fail('native disabled plugin rejected because the display key was truncated: ' + str(error))
        self.assertEqual(result, {'configuration_preserved': True, 'native_disabled_diagnostic': True})
        self.assertEqual(calls, [('plugins', 'list', '--plain', '--no-bundled'), ('plugins', 'show', runner.PLUGIN)])

    def test_similar_plugin_key_cannot_satisfy_the_exact_disabled_entry(self):
        proof, _calls, runner = self.proof(name='hermes-quota-router-other')
        with self.assertRaisesRegex(runner.Failure, 'native disabled diagnostic missing'):
            proof()

    def test_missing_plugin_still_fails(self):
        proof, _calls, runner = self.proof(name='other-plugin')
        with self.assertRaisesRegex(runner.Failure, 'native disabled diagnostic missing'):
            proof()

    def test_enabled_native_diagnostic_still_fails(self):
        proof, _calls, runner = self.proof(status='enabled')
        with self.assertRaisesRegex(runner.Failure, 'native disabled diagnostic missing'):
            proof()

    def test_configuration_drift_stops_before_native_diagnostics(self):
        proof, calls, runner = self.proof(changed=True)
        with self.assertRaisesRegex(runner.Failure, 'disabled configuration changed'):
            proof()
        self.assertEqual(calls, [])
