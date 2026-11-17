"""Optional real-YAML proof; run with an already available ruamel/native Python, never install dependencies."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests/unit'))
sys.path.insert(0, str(ROOT / 'tests/installed'))
from s3_native_consumers import ProbeGuard
from s3_fakes import TARGET, qualified
from quota_router.apply import Engine, NativeBackend
from quota_router.groups import preconditions


class NativeYamlAliasTests(unittest.TestCase):
    def test_native_yaml_alias_refuses_without_changes_and_isolated_control_restores(self):
        from ruamel.yaml import YAML
        for alias in (True, False):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / 'synthetic.yaml'
                source = ('model: &route\n  provider: openai-codex\n  default: gpt-6.1-sol\n'
                          'agent:\n  reasoning_effort: low\n')
                source += 'outside: *route\n' if alias else 'outside: {preserved: true}\n'
                path.write_text(source)
                parsed = YAML().load(source)
                self.assertEqual(bool(preconditions(parsed, 'conversation')), alias)
                backend = NativeBackend(path)
                before = path.read_bytes()
                engine = Engine(root / 'data', backend, qualified)
                engine.cycle({'conversation': TARGET}, 100)
                if alias:
                    self.assertEqual(path.read_bytes(), before)
                    self.assertIn('yaml_alias_crosses_group', engine.report(101)['groups_out']['conversation'])
                else:
                    self.assertEqual(backend.read()['model']['provider'], 'anthropic')
                    self.assertTrue(engine.restore(200))
                    restored = backend.read()
                    self.assertEqual(restored['model'], {'provider': 'openai-codex', 'default': 'gpt-6.1-sol'})
                    self.assertEqual(restored['agent']['reasoning_effort'], 'low')
                    self.assertEqual(restored['outside'], {'preserved': True})


if __name__ == '__main__':
    home = Path(os.environ['HERMES_HOME']).resolve(strict=True)
    guard = ProbeGuard(home)
    os.open = guard.wrap_open(os.open)
    sys.addaudithook(guard.audit)
    unittest.main()
