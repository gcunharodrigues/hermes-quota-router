# Regression contract: decisions/hqr-20-amendment.md, D18; installed-runner route setup and refusal assertions.
import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/unit'))
sys.path.insert(0, str(ROOT / 'tests/installed'))
from s3_fakes import Backend
import test_s3_lifecycle as fixtures
import s3_auto
from quota_router import groups, routes


def embedded(name, namespace):
    tree = ast.parse(s3_auto.EXERCISE)
    node = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), None)
    if node is None:
        raise AssertionError('Missing installed runner proof: ' + name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<installed-route-proof>', 'exec'), namespace)
    return namespace[name]


class InstalledRouteTests(unittest.TestCase):
    def test_setup_uses_the_native_default_wire_fields_instead_of_unsetting_them(self):
        backend = Backend()
        class Changes:
            def __init__(self, set=None, unset=(), **kwargs):
                self.set, self.unset = set or {}, unset
        def write_changes(path, changes):
            backend.write(changes.set, changes.unset)
        setup = embedded('prepare_native_routes', {'routes': routes, 'path': 'synthetic', 'Changes': Changes,
                                                   'write_changes': write_changes})
        setup()
        document = backend.read()
        for role in ('conversation', 'general'):
            node = document['model'] if role == 'conversation' else groups.option(document, role)
            for key, value in routes.defaults('openai-codex').items():
                self.assertEqual(node[key], value)
        self.assertEqual(backend.writes[-1][1], ())

    def test_custom_endpoint_proof_exercises_real_auto_and_off_and_rejects_optimistic_preview(self):
        helper = fixtures.AutoCommandTests()
        for optimistic in (False, True):
            with self.subTest(optimistic=optimistic), tempfile.TemporaryDirectory() as root:
                manager, _, backend = helper.manager(root)
                self.addCleanup(manager.close)
                helper.call(manager, 'config approve-map base')
                class Changes:
                    def __init__(self, set=None, document=None, **kwargs):
                        self.set, self.document = set or {}, document
                def write_changes(path, changes):
                    if changes.document is not None:
                        backend.document = changes.document
                    else:
                        backend.write(changes.set, ())
                def command(text):
                    payload = helper.call(manager, text)
                    if optimistic and text == 'explain':
                        payload['decisions']['conversation']['would_change'] = {'to': {'provider': 'anthropic'}}
                    return payload
                proof = embedded('prove_custom_route_refusal', {'copy': __import__('copy'), 'command': command,
                    'read_config_doc': lambda path: backend.read(), 'write_changes': write_changes,
                    'Changes': Changes, 'path': 'synthetic'})
                if optimistic:
                    with self.assertRaises(AssertionError):
                        proof()
                else:
                    self.assertTrue(proof())

    def test_installed_sequence_requires_native_route_apply_restore_and_refusal_before_completion(self):
        source = s3_auto.EXERCISE
        self.assertIn('prepare_native_routes()', source)
        self.assertIn("observations['native-default-route-apply']", source)
        self.assertIn("observations['native-default-route-restore']", source)
        self.assertIn("observations['custom-route-refusal'] = prove_custom_route_refusal()", source)
        self.assertLess(source.index("observations['native-default-route-restore']"),
                        source.index("observations['custom-route-refusal']"))
