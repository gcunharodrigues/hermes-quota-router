"""Real process lock contention and abrupt deaths; synthetic homes, no Docker, credentials or inference."""
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/unit'))
from s3_fakes import CONFIG, TARGET, qualified
from quota_router.apply import Engine, NativeBackend
from s3_native import install_layer

CHILD = r'''
import json, os, sys, time
from pathlib import Path
from quota_router.apply import Engine, NativeBackend
from s3_native import install_layer
root, mode, point, provider = sys.argv[1:]
root = Path(root)
count = [0]
def primitive(key):
    count[0] += 1
    if mode.endswith('crash-key') and str(count[0]) == point:
        os._exit(73)
install_layer(primitive)
def checkpoint(current):
    if current == point:
        if mode in ('crash', 'restore-crash'):
            os._exit(73)
        if mode == 'hold':
            (root / 'entered').write_text('1')
            deadline = time.monotonic() + 10
            while not (root / 'release').exists():
                if time.monotonic() > deadline:
                    os._exit(74)
                time.sleep(0.01)
selection = {'provider': provider, 'model': 'claude-opus-5-5' if provider == 'anthropic' else 'gpt-6.1-sol',
             'effort': 'high' if provider == 'anthropic' else 'xhigh'}
engine = Engine(root / 'data', NativeBackend(root / 'synthetic.json'),
                compatible=lambda: {'ok': True, 'reasons': []}, checkpoint=checkpoint)
(root / ('attempt-' + provider)).write_text('ready')
if mode.startswith('restore'):
    engine.restore(now=200)
else:
    engine.cycle({'conversation': selection}, now=100 if provider == 'anthropic' else 200)
(root / ('done-' + provider)).write_text('done')
'''


class ProcessTests(unittest.TestCase):
    def setup_root(self, root):
        root = Path(root)
        (root / 'synthetic.json').write_text(json.dumps(CONFIG))
        return root

    def spawn(self, root, mode, point, provider='anthropic'):
        env = dict(os.environ, HERMES_HOME=str(root), PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / 'tests/integration')]))
        return subprocess.Popen([sys.executable, '-c', CHILD, str(root), mode, str(point), provider], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_file(self, file, child):
        deadline = time.monotonic() + 10
        while not file.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(file.exists(), 'child did not reach the lock-held checkpoint')

    def test_two_real_processes_serialize_native_group_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.setup_root(directory)
            first = self.spawn(root, 'hold', 'journal')
            second = None
            try:
                self.wait_file(root / 'entered', first)
                second = self.spawn(root, 'normal', '-', 'openai-codex')
                self.wait_file(root / 'attempt-openai-codex', second)
                self.assertIsNone(second.poll())
                self.assertFalse((root / 'done-openai-codex').exists())
                (root / 'release').write_text('1')
                a = first.communicate(timeout=10)
                b = second.communicate(timeout=10)
                self.assertEqual((first.returncode, second.returncode), (0, 0), (a, b))
                document = json.loads((root / 'synthetic.json').read_text())
                self.assertEqual(document['model'], {'default': 'gpt-6.1-sol', 'provider': 'openai-codex',
                                                          'base_url': 'https://chatgpt.com/backend-api/codex', 'api_mode': 'codex_responses'})
                self.assertEqual(document['agent']['reasoning_effort'], 'xhigh')
                state = json.loads((root / 'data/state.json').read_text())
                self.assertEqual(state['generation'], 2)
                self.assertFalse((root / 'data/journal.json').exists())
            finally:
                for child in (first, second):
                    if child is not None and child.poll() is None:
                        child.kill()
                        child.communicate()

    def test_abrupt_death_at_each_write_point_recovers_to_coherent_group(self):
        points = [('crash', p) for p in ('journal', 'written', 'reread', 'committed', 'journal_deleted')]
        points += [('crash-key', str(n)) for n in range(1, 6)]
        for mode, point in points:
            with self.subTest(mode=mode, point=point), tempfile.TemporaryDirectory() as directory:
                root = self.setup_root(directory)
                # Ensure every field write is observable, including endpoint and API-mode removal.
                child = self.spawn(root, mode, point)
                out = child.communicate(timeout=10)
                self.assertEqual(child.returncode, 73, out)
                with mock.patch.dict(sys.modules):
                    layer = install_layer()
                    engine = Engine(root / 'data', NativeBackend(root / 'synthetic.json'), compatible=qualified)
                    engine.recover()
                    document = json.loads((root / 'synthetic.json').read_text())
                    self.assertIn(document['model']['provider'], ('openai-codex', 'anthropic'))
                    if document['model']['provider'] == 'anthropic':
                        self.assertEqual(document['model']['default'], 'claude-opus-5-5')
                    else:
                        self.assertEqual(document, CONFIG)
                    self.assertFalse((root / 'data/journal.json').exists())
                    self.assertIn(layer, ('native_config_layer_with_synthetic_storage', 'synthetic_config_layer'))

    def complete_root(self, directory):
        root = self.setup_root(directory)
        baseline = copy.deepcopy(CONFIG)
        baseline['model'].update(base_url='', api_mode='')
        baseline['agent']['reasoning_effort'] = 'low'
        (root / 'synthetic.json').write_text(json.dumps(baseline))
        return root, baseline

    def test_apply_and_restore_crashes_check_full_projection_and_state(self):
        from quota_router.groups import project, target
        points = [('crash', point) for point in ('journal', 'written', 'reread', 'committed', 'journal_deleted')]
        points += [('crash-key', str(n)) for n in range(1, 6)]
        for restoring in (False, True):
            for mode, point in points:
                with self.subTest(restoring=restoring, mode=mode, point=point), tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules):
                    root, baseline = self.complete_root(directory)
                    writes = []
                    install_layer(writes.append)
                    engine = Engine(root / 'data', NativeBackend(root / 'synthetic.json'), qualified)
                    if restoring:
                        engine.cycle({'conversation': TARGET}, 100)
                    prior = json.loads((root / 'synthetic.json').read_text())
                    wanted = project(baseline, 'conversation') if restoring else target('conversation', TARGET)
                    child = self.spawn(root, 'restore-' + mode if restoring else mode, point)
                    out = child.communicate(timeout=10)
                    self.assertEqual(child.returncode, 73, out)
                    recovered = Engine(root / 'data', NativeBackend(root / 'synthetic.json'), qualified)
                    self.assertTrue(recovered.recover())
                    current = json.loads((root / 'synthetic.json').read_text())
                    expected = project(prior, 'conversation') if mode == 'crash' and point == 'journal' else wanted
                    self.assertEqual(project(current, 'conversation'), expected)
                    state = json.loads((root / 'data/state.json').read_text())
                    entry = state['groups']['conversation']
                    self.assertEqual(entry['baseline'], project(baseline, 'conversation'))
                    self.assertEqual(entry['last'], expected)
                    self.assertEqual(state['generation'], 1 if restoring or expected == wanted else 0)
                    if restoring and expected == wanted:
                        self.assertTrue(entry['restored'])
                        self.assertFalse(entry['active'])
                    self.assertFalse((root / 'data/journal.json').exists())
                    self.assertTrue(recovered.recover())
                    self.assertEqual(recovered.state, state)

    def test_post_crash_prior_and_third_edits_are_preserved(self):
        from quota_router.groups import project
        for restoring in (False, True):
            for edit in ('all-prior', 'third'):
                with self.subTest(restoring=restoring, edit=edit), tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules):
                    root, baseline = self.complete_root(directory)
                    writes = []
                    install_layer(writes.append)
                    engine = Engine(root / 'data', NativeBackend(root / 'synthetic.json'), qualified)
                    if restoring:
                        engine.cycle({'conversation': TARGET}, 100)
                    prior = json.loads((root / 'synthetic.json').read_text())
                    child = self.spawn(root, 'restore-crash-key' if restoring else 'crash-key', '2')
                    out = child.communicate(timeout=10)
                    self.assertEqual(child.returncode, 73, out)
                    state_before = json.loads((root / 'data/state.json').read_text())
                    changed = copy.deepcopy(prior)
                    if edit == 'third':
                        changed['model']['default'] = 'gpt-6.1-terra'
                    (root / 'synthetic.json').write_text(json.dumps(changed))
                    before = (root / 'synthetic.json').read_bytes()
                    count = len(writes)
                    recovered = Engine(root / 'data', NativeBackend(root / 'synthetic.json'), qualified)
                    self.assertTrue(recovered.recover())
                    self.assertEqual((root / 'synthetic.json').read_bytes(), before)
                    self.assertEqual(len(writes), count)
                    entry = recovered.state['groups']['conversation']
                    self.assertEqual(entry['baseline'], project(baseline, 'conversation'))
                    self.assertEqual(entry['last'], state_before['groups']['conversation']['last'])
                    self.assertEqual(recovered.state['generation'], state_before['generation'])
                    self.assertEqual(recovered.state['history'], state_before['history'])
                    if edit == 'third':
                        self.assertFalse(entry['active'])
                        self.assertIn('model.default', entry['excluded'])
                    self.assertFalse((root / 'data/journal.json').exists())

    def test_native_seam_secret_aliases_never_reach_state_or_status(self):
        for alias in ('api_key', 'api', 'key_env', 'api_key_env'):
            for later in (False, True):
                with self.subTest(alias=alias, later=later), tempfile.TemporaryDirectory() as directory, mock.patch.dict(sys.modules):
                    root = self.setup_root(directory)
                    install_layer()
                    engine = Engine(root / 'data', NativeBackend(root / 'synthetic.json'), compatible=qualified)
                    if later:
                        engine.cycle({'conversation': TARGET}, now=100)
                    cfg = json.loads((root / 'synthetic.json').read_text())
                    cfg['model'][alias] = 'SYNTHETIC_PRIVATE_VALUE'
                    (root / 'synthetic.json').write_text(json.dumps(cfg))
                    before = (root / 'synthetic.json').read_bytes()
                    engine.cycle({'conversation': TARGET}, now=200)
                    engine.restore(now=300)
                    self.assertEqual((root / 'synthetic.json').read_bytes(), before)
                    text = repr(engine.report(301)) + ''.join(p.read_text() for p in (root / 'data').glob('*.json'))
                    self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', text)


if __name__ == '__main__':
    unittest.main()
