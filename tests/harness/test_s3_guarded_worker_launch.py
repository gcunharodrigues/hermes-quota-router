"""HQR-32: actual guarded workers must not select the forbidden posix_spawn path."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

INSTALLED = Path(__file__).resolve().parents[1] / 'installed'
DRIVER = r'''
import json, os, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from s3_native_consumers import ProbeGuard, UnsafeProbe, Worker
native = SimpleNamespace(root=Path(sys.argv[2]), function=lambda *args: None)
snapshot = {'model': {'default': 'synthetic-model', 'provider': 'synthetic-provider'},
            'agent': {'reasoning_effort': 'low'}, 'delegation': {'backend': 'synthetic'}}
# Reproduce the Docker interpreter's CLOSEFROM-capable posix_spawn selection on the local Python.
subprocess._USE_POSIX_SPAWN = True
subprocess._HAVE_POSIX_SPAWN_CLOSEFROM = True
def observed_spawn(self, args, executable, env, *rest):
    sys.audit('os.posix_spawn', executable, args, os.environ if env is None else env)
    raise AssertionError('forbidden posix_spawn reached the execution boundary')
subprocess.Popen._posix_spawn = observed_spawn
guard = ProbeGuard(os.environ['HERMES_HOME'])
sys.addaudithook(guard.audit)
worker = Worker(native, guard, snapshot)
try:
    result = worker.read()
finally:
    worker.close()
assert guard.denied == [], guard.denied
# Direct spawn and unrelated Popen remain refused before they can create any child.
for operation in (lambda: os.posix_spawn(sys.executable, [sys.executable, '-c', 'raise SystemExit(99)'], dict(os.environ)),
                  lambda: subprocess.Popen([sys.executable, '-c', 'raise SystemExit(98)'])):
    try:
        operation()
    except UnsafeProbe:
        pass
    else:
        raise AssertionError('unrelated subprocess was not refused')
assert guard.denied == ['os.posix_spawn', 'subprocess.Popen'], guard.denied
print(json.dumps({'result': result, 'negative_controls': guard.denied}), flush=True)
'''


class GuardedWorkerLaunchTests(unittest.TestCase):
    def test_real_worker_avoids_spawn_without_relaxing_the_parent_audit_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, native = root / 'home', root / 'native'
            home.mkdir()
            modules = {
                'agent/__init__.py': '',
                'agent/safe_worker_policy.py': 'snapshot = None\ndef _bind_worker_config(value):\n    global snapshot\n    snapshot = value\n',
                'hermes_cli/__init__.py': '',
                'hermes_cli/config.py': 'def load_config_readonly():\n    from agent.safe_worker_policy import snapshot\n    return snapshot\n',
                'hermes_constants.py': "def resolve_reasoning_config(cfg, model):\n    return {'enabled': True, 'effort': cfg['agent']['reasoning_effort']}\n",
                'tools/__init__.py': '',
                'tools/delegate_tool_config.py': "def _load_config():\n    from agent.safe_worker_policy import snapshot\n    return snapshot['delegation']\n",
            }
            for name, source in modules.items():
                path = native / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            env = {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'HERMES_HOME': str(home), 'TMPDIR': directory}
            proc = subprocess.run([sys.executable, '-I', '-B', '-c', DRIVER, str(INSTALLED), str(native)],
                                  env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stderr, '')
            self.assertEqual(json.loads(proc.stdout), {
                'result': {'route': {'provider': 'synthetic-provider', 'model': 'synthetic-model', 'effort': 'low'},
                           'delegation': {'backend': 'synthetic'}},
                'negative_controls': ['os.posix_spawn', 'subprocess.Popen']})
            self.assertEqual(sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()),
                             sorted('native/' + name for name in modules))
