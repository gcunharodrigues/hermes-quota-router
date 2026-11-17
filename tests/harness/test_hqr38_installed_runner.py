"""HQR-38 installed-runner contract for the safety net groups (decisions/hqr-38-spec.md, acceptance tests).

The embedded proof runs here against the real engine with a synthetic backend; the installed target run is separate and authorized apart.
"""
import ast
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/unit'))
sys.path.insert(0, str(ROOT / 'tests/installed'))
from s2_fakes import NOW, claude, codex, reader_for
from s3_fakes import Backend, CONFIG, qualified
from test_s3_lifecycle import AutoContext
import s3_auto
from quota_router import groups
from quota_router.lifecycle import Management

PROOF = 'prove_safety_net_groups'


def embedded(name, namespace):
    tree = ast.parse(s3_auto.EXERCISE)
    node = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), None)
    if node is None:
        raise AssertionError('Missing installed runner proof: ' + name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<installed-safety-net-proof>', 'exec'), namespace)
    return namespace[name]


def stand_in_chain(document, role):
    """Local stand-in for the native readers; the installed run uses get_fallback_chain and the route inheritance."""
    if role == 'conversation':
        return list(document.get('fallback_providers') or [])
    return list(groups.option(document, role).get('fallback_providers') or [])


class Changes:
    def __init__(self, set=None, document=None, **kwargs):
        self.set, self.document = set or {}, document


class SafetyNetRunnerTests(unittest.TestCase):
    def run_proof(self, *, native_chain=stand_in_chain, after=None):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            manager = Management(AutoContext(), importer=lambda: reader_for(openai_codex=codex(10), anthropic=claude(80)),
                                 sources=lambda: (backend.read(), []), clock=lambda: NOW, profile=lambda: 'default',
                                 backend=backend, data_dir=Path(root), compatible=qualified)
            try:
                def command(text):
                    payload = json.loads(manager.command(text + ' --json'))
                    assert payload['ok'], payload.get('error')
                    if after is not None:
                        after(text, payload, backend)
                    return payload
                def write_changes(_path, changes):
                    if changes.document is not None:
                        backend.document = copy.deepcopy(changes.document)
                    else:
                        backend.write(changes.set, ())
                command('config approve-map base')
                proof = embedded(PROOF, {'copy': copy, 'command': command, 'read_config_doc': lambda _path: backend.read(),
                                         'write_changes': write_changes, 'Changes': Changes, 'path': 'synthetic',
                                         'groups': groups, 'manager': manager, 'rest': copy.deepcopy})
                result = proof(native_chain)
                return result, backend.read()
            finally:
                manager.close()

    def test_proof_covers_root_and_route_readback_off_restore_and_external_edit(self):
        result, final = self.run_proof()
        self.assertEqual(result, {'apply-readback': True, 'off-restore-absent': True, 'off-restore-present': True,
                                  'external-edit-exclusion': True})
        self.assertEqual(final, CONFIG)

    def test_proof_rejects_a_native_reader_that_disagrees(self):
        with self.assertRaises(AssertionError):
            self.run_proof(native_chain=lambda document, role: [])

    def test_proof_rejects_an_off_that_leaves_the_chain(self):
        def leave(text, _payload, backend):
            if text == 'mode off':
                backend.write({'fallback_providers': [{'provider': 'anthropic', 'model': 'claude-opus-5-5'}]}, ())
        with self.assertRaises(AssertionError):
            self.run_proof(after=leave)

    def test_proof_rejects_a_status_without_safety_net_groups(self):
        def hide(text, payload, _backend):
            if text == 'status':
                payload['applied']['safety_net'] = {}
        with self.assertRaises((AssertionError, KeyError)):
            self.run_proof(after=hide)

    def test_installed_sequence_uses_native_readers_and_runs_before_custom_refusal(self):
        source = s3_auto.EXERCISE
        call = "observations['safety-net-groups'] = prove_safety_net_groups(native_chain)"
        # assertTrue keeps the long embedded source out of the failure message.
        for needle in (call, 'from hermes_cli.fallback_config import get_fallback_chain', '_with_inherited_fallback'):
            self.assertTrue(needle in source, needle)
        self.assertLess(source.index("observations['native-default-route-restore']"), source.index(call))
        self.assertLess(source.index(call), source.index("observations['custom-route-refusal']"))


if __name__ == '__main__':
    unittest.main()
