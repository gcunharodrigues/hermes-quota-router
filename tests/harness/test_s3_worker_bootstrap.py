"""HQR-32 TEST-01: execute the real Worker payload with inert native modules."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

INSTALLED = Path(__file__).resolve().parents[1] / 'installed'
DRIVER = r'''
import json, os, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from s3_native_consumers import ProbeGuard, Worker
native = SimpleNamespace(root=Path(sys.argv[2]), function=lambda *args: None)
snapshot = {'model': {'default': 'synthetic-model', 'provider': 'synthetic-provider'},
            'agent': {'reasoning_effort': 'low'}, 'delegation': {'backend': 'synthetic'}}
worker = Worker(native, ProbeGuard(os.environ['HERMES_HOME']), snapshot)
try:
    print(json.dumps(worker.read()), flush=True)
finally:
    worker.close()
'''


class WorkerBootstrapTests(unittest.TestCase):
    def test_real_worker_exec_bootstraps_guard_and_resolves_inert_modules(self):
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
                'route': {'provider': 'synthetic-provider', 'model': 'synthetic-model', 'effort': 'low'},
                'delegation': {'backend': 'synthetic'}})
            self.assertEqual(sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()),
                             sorted('native/' + name for name in modules))
