# Contract: decisions/aux-plan.md, AUXP-04/H15b and H2/H3/H9 through Management, not a substitute caller.
"""Real local processes; synthetic native Changes seam, deterministic readings, no host or network access."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
CHILD = r'''
import json, os, sys, time
from pathlib import Path
from quota_router.lifecycle import Management
from quota_router.apply import NativeBackend
from quota_router.mapping import approved_base, approved_auxiliary
from s2_fakes import NOW, codex, claude, reader_for
from s3_native import install_layer
root, provider, mode, point = sys.argv[1:]
root = Path(root)
install_layer()
class Registration:
    def dispose(self): pass
class Context:
    def __init__(self):
        self.settings = {'roles': approved_base(), 'auxiliary_map': approved_auxiliary(),
                         'consumers.auxiliary': True, 'consumers.subagents': False}
    def get_config(self, key, default=None): return self.settings.get(key, default)
    def set_config(self, key, value): self.settings[key] = value
    def register_hook(self, *args, **kwargs): return Registration()
ctx = Context()
backend = NativeBackend(root / 'config.json')
reader = reader_for(openai_codex=codex(100 if provider == 'anthropic' else 10),
                    anthropic=claude(10 if provider == 'anthropic' else 100))
(root / ('attempt-' + provider)).write_text('1')
m = Management(ctx, importer=lambda: reader, sources=lambda: (backend.read(), []), clock=lambda: NOW,
               profile=lambda: 'default', backend=backend, data_dir=root / 'data',
               compatible=lambda: {'ok': True}, auxiliary_compatible=lambda: {'ok': True}, catalogs=lambda: {},
               auxiliary_registry=lambda: {'ok': True, 'tasks': {}})
original = m.start_auto
def start():
    result = original()
    def main_checkpoint(value):
        if value == 'main_cycle_done':
            (root / ('decision-' + provider)).write_text(json.dumps(backend.read()['model']))
            if mode == 'hold':
                (root / 'entered').write_text('1')
                deadline = time.monotonic() + 10
                while not (root / 'release').exists():
                    if time.monotonic() > deadline: os._exit(74)
                    time.sleep(.01)
    m.engine.checkpoint = main_checkpoint
    def aux_checkpoint(value):
        if mode == 'crash' and value == point: os._exit(73)
    m.aux_engine.checkpoint = aux_checkpoint
    return result
m.start_auto = start
result = json.loads(m.command('mode auto --json'))
assert result['ok'], result
if mode == 'restore':
    ctx.settings['auxiliary_map'] = {}
    m.auxiliary_registry = lambda: {'ok': False}
    m.catalogs = lambda: {'anthropic': []}
    result = json.loads(m.command('mode off --json'))
    assert result['ok'], result
    assert not result['applied']['auxiliary']['restoration_pending'], result
(root / ('done-' + provider)).write_text(json.dumps(result))
m.close()
'''


class AuxiliaryManagementProcessTests(unittest.TestCase):
    def baseline(self):
        from quota_router.mapping import approved_auxiliary
        return {'model': {'provider': 'openai-codex', 'default': 'gpt-6.1-sol'},
                'agent': {'reasoning_effort': 'high'}, 'untouched': {'keep': True},
                'auxiliary': {task: {'provider': 'openai-codex', 'model': pair['openai-codex']['model']}
                              for task, pair in approved_auxiliary().items()}}

    def spawn(self, root, provider='anthropic', mode='normal', point='-'):
        env = dict(os.environ, HERMES_HOME=str(root), PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / 'tests/unit'), str(ROOT / 'tests/integration'))))
        return subprocess.Popen([sys.executable, '-c', CHILD, str(root), provider, mode, point],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_file(self, path, child):
        deadline = time.monotonic() + 10
        while not path.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(path.exists(), 'Management did not reach synthetic checkpoint')

    def test_second_management_cannot_decide_between_main_and_auxiliary_cycles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = self.baseline()
            (root / 'config.json').write_text(json.dumps(baseline))
            first = self.spawn(root, mode='hold')
            second = None
            try:
                self.wait_file(root / 'entered', first)
                intermediate = json.loads((root / 'config.json').read_text())
                self.assertEqual(intermediate['model']['provider'], 'anthropic')
                self.assertEqual(intermediate['auxiliary'], baseline['auxiliary'])
                second = self.spawn(root, provider='openai-codex')
                self.wait_file(root / 'attempt-openai-codex', second)
                self.assertIsNone(second.poll())
                self.assertFalse((root / 'decision-openai-codex').exists())
                (root / 'release').write_text('1')
                outputs = first.communicate(timeout=15), second.communicate(timeout=15)
                self.assertEqual((first.returncode, second.returncode), (0, 0), outputs)
                final = json.loads((root / 'config.json').read_text())
                self.assertEqual(final['model']['provider'], 'openai-codex')
                self.assertTrue(all(node['provider'] == 'openai-codex' for node in final['auxiliary'].values()))
                self.assertEqual(final['untouched'], baseline['untouched'])
                self.assertFalse((root / 'data/aux-journal.json').exists())
            finally:
                for child in (first, second):
                    if child is not None and child.poll() is None:
                        child.kill()
                        child.communicate()

    def test_actual_lifecycle_recovers_auxiliary_crashes_then_off_restores_absent_keys(self):
        for point in ('journal', 'written', 'committed'):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                baseline = self.baseline()
                (root / 'config.json').write_text(json.dumps(baseline))
                child = self.spawn(root, mode='crash', point=point)
                output = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 73, output)
                self.assertTrue((root / 'data/aux-journal.json').exists())
                child = self.spawn(root, mode='restore')
                output = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, output)
                self.assertEqual(json.loads((root / 'config.json').read_text()), baseline)
                self.assertFalse((root / 'data/aux-journal.json').exists())
                self.assertFalse((root / 'data/journal.json').exists())
