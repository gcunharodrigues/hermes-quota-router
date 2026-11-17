"""SEC-S3-06: exercise ADVANCED_CHECK at the native scanner's inspected Git seam."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))

# Inert host modules model only the inspected scanner call, not the full native scanner.
DRIVER = r'''
import json, os, subprocess, sys, types
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import s3_auto
home = Path(sys.argv[2])
os.environ['HERMES_HOME'] = str(home)
backend = types.ModuleType('hermes_cli.config_backend')
backend.__file__ = str(home / 'source/hermes_cli/config_backend.py')
backend.read_config_doc = lambda path: json.loads(Path(path).read_text())
config = types.ModuleType('hermes_cli.config')
config.get_config_path = lambda: home / 'config.yaml'
scanner = types.ModuleType('tools.plugin_guard')
def scan_plugin(plugin_dir, *, source):
    out = subprocess.run(
        ['git', '-c', 'core.fsmonitor=false', '-C', str(plugin_dir), 'ls-files', '-z', '--', '*.pyc', '*.pyo'],
        capture_output=True, check=True, timeout=60, stdin=subprocess.DEVNULL).stdout
    return types.SimpleNamespace(verdict='unsafe' if out else 'safe')
scanner.scan_plugin = scan_plugin
sys.modules.update({'hermes_cli.config_backend': backend, 'hermes_cli.config': config, 'tools.plugin_guard': scanner})
exec(compile(s3_auto.ADVANCED_CHECK, '<advanced-check-fixture>', 'exec'))
# The guard stays enabled and scanner-only permissions must not survive the scan.
command = ('git', '-c', 'core.fsmonitor=false', '-C', str(home / 'plugins/advanced-delegation'),
           'ls-files', '-z', '--', '*.pyc', '*.pyo')
for event, args in [('open', (os.devnull, None, os.O_RDWR)),
                    ('subprocess.Popen', ('git', command, None, None))]:
    try:
        _guard.audit(event, args)
    except _native.UnsafeProbe:
        pass
    else:
        raise AssertionError('scanner capability leaked after ADVANCED_CHECK')
'''


class ScannerGuardTests(unittest.TestCase):
    def check_fixture(self, *, bytecode=False):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root = home / 'plugins/advanced-delegation'
            root.mkdir(parents=True)
            (root / 'model_map.py').write_text('# synthetic scanner fixture\n')
            if bytecode:
                (root / 'tracked.pyc').write_bytes(b'synthetic shipped bytecode')
            (home / 'config.yaml').write_text('{}')
            for args in (('init', '-q'), ('add', '--', 'plugins/advanced-delegation')):
                subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-C', directory, *args],
                               check=True, capture_output=True)
            files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
            expected = {'ref': '13b2c1c9c8204bf333df240b2aacf98c3e6250b7', 'files': files}
            proc = subprocess.run([sys.executable, '-B', '-c', DRIVER, str(Path(__file__).resolve().parents[1] / 'installed'), directory],
                                  input=json.dumps(expected), capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout.strip())
            self.assertTrue(result['bytes_match'])
            self.assertEqual(result['special'], [])
            self.assertTrue(result['scan_on_install'])
            return result

    def test_advanced_check_executes_scanner_readonly_git_with_devnull(self):
        self.assertEqual(self.check_fixture()['verdict'], 'safe')

    def test_advanced_check_still_observes_tracked_bytecode(self):
        self.assertEqual(self.check_fixture(bytecode=True)['verdict'], 'unsafe')

    def test_scanner_capability_is_exact_scoped_and_revoked_on_failure(self):
        module = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as directory:
            guard = module.ProbeGuard(directory)
            self.assertTrue(hasattr(guard, 'scanner_git'), 'scoped scanner Git admission missing')
            root = Path(directory) / 'plugins/advanced-delegation'
            root.mkdir(parents=True)
            command = ('git', '-c', 'core.fsmonitor=false', '-C', str(root), 'ls-files', '-z', '--', '*.pyc', '*.pyo')
            null = ('open', (os.devnull, None, os.O_RDWR))
            popen = ('subprocess.Popen', ('git', command, None, None))
            for event, args in (null, popen):
                with self.assertRaises(module.UnsafeProbe):
                    guard.audit(event, args)
            with self.assertRaisesRegex(RuntimeError, 'synthetic scanner failure'):
                with guard.scanner_git(root):
                    guard.audit(*null)
                    guard.audit('open', (os.devnull, None, os.O_RDWR | os.O_CLOEXEC))
                    guard.audit(*popen)
                    invalid = [('open', (os.devnull, None, os.O_RDWR | os.O_TRUNC)),
                               ('open', ('/dev/zero', None, os.O_RDWR)),
                               ('open', ('/foreign/scanner-output', None, os.O_RDWR)),
                               ('subprocess.Popen', ('git', command + ('--cached',), None, None)),
                               ('subprocess.Popen', ('git', command, '/foreign', None)),
                               ('subprocess.Popen', ('git', ('git', 'status'), None, None)),
                               ('socket.connect', (None, ('192.0.2.1', 443))),
                               ('open', (str(Path(directory) / 'auth.json'), None, os.O_RDONLY))]
                    for event, args in invalid:
                        with self.subTest(event=event, args=args), self.assertRaises(module.UnsafeProbe):
                            guard.audit(event, args)
                    raise RuntimeError('synthetic scanner failure')
            for event, args in (null, popen):
                with self.assertRaises(module.UnsafeProbe):
                    guard.audit(event, args)
            self.assertEqual(guard.readonly_commands, set())
            with self.assertRaises(module.ProbeFailure):
                with guard.scanner_git(Path(directory).parent):
                    self.fail('foreign scanner root admitted')
