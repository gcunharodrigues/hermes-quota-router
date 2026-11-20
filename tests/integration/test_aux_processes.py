# decisions/aux-plan.md, H15a/H15b/H15c: real processes and abrupt death through the actual Engine.
"""Additional infrastructure verification; synthetic native storage seam, no host qualification or lifecycle Auto."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from quota_router import auxiliary, groups
from quota_router.apply import Engine, NativeBackend, locked_pair
from s3_native import install_layer

ROOT = Path(__file__).resolve().parents[2]
BASE = {'model': {'provider': 'openai-codex', 'default': 'gpt-6.1-sol'}, 'agent': {'reasoning_effort': 'high'},
        'auxiliary': {'approval': {'provider': 'openai-codex', 'model': 'gpt-6.1-terra', 'base_url': '', 'api_mode': '',
                                   'timeout': 41, 'fallback_chain': ['synthetic']}}, 'untouched': {'keep': True}}
CHILD = r'''
import json, os, sys, time
from pathlib import Path
from quota_router.apply import Engine, NativeBackend, locked_pair
from s3_native import install_layer
root, mode, point, provider = sys.argv[1:]
root = Path(root)
count = [0]
def primitive(key):
    count[0] += 1
    if mode == 'key' and str(count[0]) == point:
        os._exit(73)
install_layer(primitive)
def barrier():
    (root / 'entered').write_text('1')
    deadline = time.monotonic() + 10
    while not (root / 'release').exists():
        if time.monotonic() > deadline:
            os._exit(74)
        time.sleep(.01)
def checkpoint(value):
    if mode == 'crash' and value == point:
        os._exit(73)
backend = NativeBackend(root / 'config.json')
main = Engine(root / 'data', backend, lambda: {'ok': True})
aux = Engine(root / 'data', backend, lambda: {'ok': True}, checkpoint=checkpoint,
             kind='auxiliary', state_name='aux-state.json', journal_name='aux-journal.json')
(root / ('attempt-' + provider)).write_text('1')
with locked_pair(main, aux):
    assert main.recover_locked() and aux.recover_locked()
    # This is a synthetic caller decision, read and recorded inside the same real lock as both cycles.
    document = backend.read()
    (root / ('decision-' + provider)).write_text(json.dumps(document['model']))
    if mode == 'restore':
        assert aux.restore_locked(200)
    elif mode in ('crash', 'key'):
        aux.cycle_locked({'aux:approval': {'provider': provider, 'model': 'claude-sonnet-5-5', 'effort': 'low'}}, 100)
    else:
        main.cycle_locked({'conversation': {'provider': provider,
            'model': 'claude-opus-5-5' if provider == 'anthropic' else 'gpt-6.1-sol', 'effort': 'high'}}, 100)
        if mode == 'hold':
            barrier()
        aux.cycle_locked({'aux:approval': {'provider': provider,
            'model': 'claude-sonnet-5-5' if provider == 'anthropic' else 'gpt-6.1-terra', 'effort': 'low'}}, 100)
(root / ('done-' + provider)).write_text('1')
'''


def pair(root):
    backend = NativeBackend(root / 'config.json')
    return (Engine(root / 'data', backend, lambda: {'ok': True}),
            Engine(root / 'data', backend, lambda: {'ok': True}, kind='auxiliary',
                   state_name='aux-state.json', journal_name='aux-journal.json'))


class AuxiliaryProcessTests(unittest.TestCase):
    def spawn(self, root, mode, point='-', provider='anthropic'):
        env = dict(os.environ, HERMES_HOME=str(root),
                   PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / 'tests/integration'))))
        return subprocess.Popen([sys.executable, '-c', CHILD, str(root), mode, point, provider], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_file(self, file, child):
        deadline = time.monotonic() + 10
        while not file.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(file.exists(), 'child did not reach synthetic barrier')

    def test_opposite_decision_waits_between_main_and_auxiliary_cycles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config.json').write_text(json.dumps(BASE))
            first = self.spawn(root, 'hold')
            second = None
            try:
                self.wait_file(root / 'entered', first)
                second = self.spawn(root, 'normal', provider='openai-codex')
                self.wait_file(root / 'attempt-openai-codex', second)
                self.assertIsNone(second.poll())
                self.assertFalse((root / 'decision-openai-codex').exists())
                self.assertFalse((root / 'done-openai-codex').exists())
                intermediate = json.loads((root / 'config.json').read_text())
                self.assertEqual(intermediate['model']['provider'], 'anthropic')
                self.assertEqual(intermediate['auxiliary']['approval']['provider'], 'openai-codex')
                (root / 'release').write_text('1')
                a, b = first.communicate(timeout=10), second.communicate(timeout=10)
                self.assertEqual((first.returncode, second.returncode), (0, 0), (a, b))
                decided = json.loads((root / 'decision-openai-codex').read_text())
                self.assertEqual(decided['provider'], 'anthropic')
                final = json.loads((root / 'config.json').read_text())
                self.assertEqual(final['model']['provider'], 'openai-codex')
                self.assertEqual(final['auxiliary']['approval']['provider'], 'openai-codex')
                self.assertEqual(final['untouched'], BASE['untouched'])
                main_state = json.loads((root / 'data/state.json').read_text())
                aux_state = json.loads((root / 'data/aux-state.json').read_text())
                self.assertEqual((main_state['generation'], aux_state['generation']), (2, 2))
                self.assertFalse((root / 'data/journal.json').exists())
                self.assertFalse((root / 'data/aux-journal.json').exists())
            finally:
                for child in (first, second):
                    if child is not None and child.poll() is None:
                        child.kill()
                        child.communicate()

    def test_abrupt_death_each_aux_checkpoint_and_key_recovers_then_restores_exact_absence(self):
        points = [('crash', p) for p in ('journal', 'written', 'reread', 'committed', 'journal_deleted')]
        points += [('key', str(n)) for n in range(1, 6)]
        for mode, point in points:
            with self.subTest(mode=mode, point=point), tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules):
                root = Path(directory)
                (root / 'config.json').write_text(json.dumps(BASE))
                child = self.spawn(root, mode, point)
                output = child.communicate(timeout=10)
                self.assertEqual(child.returncode, 73, output)
                layer = install_layer()
                self.assertEqual(layer, 'synthetic_config_layer')
                main, aux = pair(root)
                with locked_pair(main, aux):
                    self.assertTrue(main.recover_locked())
                    self.assertTrue(aux.recover_locked())
                    current = json.loads((root / 'config.json').read_text())
                    expected = (auxiliary.project(BASE, 'aux:approval') if mode == 'crash' and point == 'journal'
                                else auxiliary.target('aux:approval', {'provider': 'anthropic', 'model': 'claude-sonnet-5-5',
                                                                      'effort': 'low'}, auxiliary.project(BASE, 'aux:approval')))
                    self.assertEqual(auxiliary.project(current, 'aux:approval'), expected)
                    self.assertEqual(aux.state['groups']['aux:approval']['baseline'], auxiliary.project(BASE, 'aux:approval'))
                    self.assertFalse(aux.read_record(aux.journal_name))
                    state = copy.deepcopy(aux.state)
                    self.assertTrue(aux.recover_locked())
                    self.assertEqual(aux.state, state)
                    self.assertTrue(aux.restore_locked(300))
                    self.assertEqual(json.loads((root / 'config.json').read_text()), BASE)
                    self.assertEqual(main.state['groups'], {})

    def test_restore_crash_keeps_main_journal_and_other_options_unchanged(self):
        # Restore intent recovery uses no approved map, catalog or plugin registry.
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules):
            root = Path(directory)
            (root / 'config.json').write_text(json.dumps(BASE))
            install_layer()
            main, aux = pair(root)
            with locked_pair(main, aux):
                aux.cycle_locked({'aux:approval': {'provider': 'anthropic', 'model': 'claude-sonnet-5-5', 'effort': 'low'}}, 100)
            main_before = (root / 'data/state.json').read_bytes() if (root / 'data/state.json').exists() else None
            child_code = CHILD.replace("if mode == 'crash' and value == point:", "if mode == 'restore' and value == point:")
            for point in ('journal', 'written', 'reread', 'committed', 'journal_deleted'):
                with locked_pair(main, aux):
                    aux.cycle_locked({'aux:approval': {'provider': 'anthropic', 'model': 'claude-sonnet-5-5', 'effort': 'low'}}, 100)
                env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT), str(ROOT / 'tests/integration'))))
                result = subprocess.run([sys.executable, '-c', child_code, str(root), 'restore', point, 'anthropic'],
                                        env=env, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 73, result.stderr)
                with locked_pair(main, aux):
                    self.assertTrue(aux.recover_locked())
                    self.assertTrue(aux.restore_locked(300))
                    self.assertEqual(json.loads((root / 'config.json').read_text()), BASE)
                self.assertEqual((root / 'data/state.json').read_bytes() if (root / 'data/state.json').exists() else None, main_before)
