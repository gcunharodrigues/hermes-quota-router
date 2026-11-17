"""HQR-32 RUN-01: refuse replacement and reuse only an attested inactive dependency."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

INSTALLED = Path(__file__).resolve().parents[1] / 'installed'
sys.path.insert(0, str(INSTALLED))
# Inert modules cover the native existing-destination refusal and pin seam, not the whole installer.
DRIVER = r'''
import json, os, sys, types
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import s3_auto
home = Path(os.environ['HERMES_HOME'])
backend = types.ModuleType('hermes_cli.config_backend')
backend.__file__ = str(home / 'source/hermes_cli/config_backend.py')
backend.read_config_doc = lambda path: json.loads(Path(path).read_text())
config = types.ModuleType('hermes_cli.config')
config.get_config_path = lambda: home / 'config.yaml'
scanner = types.ModuleType('tools.plugin_guard')
scanner.scan_plugin = lambda *a, **k: types.SimpleNamespace(verdict=json.loads((home / 'scanner.json').read_text()))
git = types.ModuleType('hermes_cli.plugins_cmd_git')
git.pinned_revision = lambda name: json.loads((home / 'pin.json').read_text())
sys.modules.update({'hermes_cli.config_backend': backend, 'hermes_cli.config': config,
                    'hermes_cli.plugins_cmd_git': git, 'tools.plugin_guard': scanner})
exec(compile(s3_auto.ADVANCED_CHECK, '<advanced-reuse-fixture>', 'exec'))
'''


class DependencyReuseTests(unittest.TestCase):
    def fixture(self, *, enabled=False, pin=None, mutation=None, verdict: str | None = 'safe'):
        runner = importlib.import_module('s3_auto')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home = Path(temporary.name)
        root = home / 'plugins/advanced-delegation'
        root.mkdir(parents=True)
        (root / 'model_map.py').write_text('# inert dependency\n')
        files = {'model_map.py': hashlib.sha256((root / 'model_map.py').read_bytes()).hexdigest()}
        (home / 'pin.json').write_text(json.dumps(runner.ADVANCED_REF if pin is None else pin))
        (home / 'scanner.json').write_text(json.dumps(verdict))
        (home / 'config.yaml').write_text(json.dumps({'plugins': {'enabled': ['advanced-delegation'] if enabled else []}}))
        if mutation == 'bytes':
            (root / 'model_map.py').write_text('# tampered\n')
        elif mutation == 'extra':
            (root / 'extra.py').write_text('# unexpected\n')
        elif mutation == 'link':
            (root / 'linked').symlink_to(root / 'model_map.py')
        elif mutation == 'special':
            os.mkfifo(root / 'pipe')
        elif mutation == 'root-link':
            root.rename(root.with_name('actual'))
            root.symlink_to(root.with_name('actual'), target_is_directory=True)
        class Run:
            advanced_manifest = {'ref': runner.ADVANCED_REF, 'files': files}
            def __init__(self):
                self.calls, self.attestations = [], []
            def hermes(self, *args):
                self.calls.append(args)
                if args[1] == 'install':
                    # Native _install_plugin_core refuses an existing target without --force.
                    raise runner.Failure("Plugin 'advanced-delegation' already exists. Use force reinstall or run `hermes plugins update advanced-delegation`.")
                if args[1] == 'show':
                    return SimpleNamespace(stdout='Status: enabled' if enabled else 'Status: not enabled')
                return SimpleNamespace(returncode=0)
            def json(self, script, **kwargs):
                if script == runner.ADVANCED_CHECK:
                    self.attestations.append(json.loads(kwargs['stdin']))
                    env = {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'HERMES_HOME': str(home), 'TMPDIR': str(home)}
                    proc = subprocess.run([sys.executable, '-I', '-B', '-c', DRIVER, str(INSTALLED)],
                                          input=kwargs['stdin'], env=env, capture_output=True, text=True, timeout=20)
                    if proc.returncode:
                        raise runner.Failure('dependency attestation failed')
                    return json.loads(proc.stdout)
                return {'version': runner.ADVANCED_VERSION, 'backend': 'model_map', 'loaded': True}
        return runner, Run()

    def test_native_existing_destination_refusal_reuses_exact_inactive_tree(self):
        runner, run = self.fixture()
        result = runner.install_advanced(run)
        self.assertTrue(result['loaded'])
        self.assertTrue(result['reused'])
        self.assertEqual([call[1] for call in run.calls], ['install', 'show', 'enable'])
        self.assertEqual(len(run.attestations), 1)
        self.assertTrue(run.attestations[0]['reuse'])
        self.assertFalse(any('--force' in call for call in run.calls))

    def test_enabled_dependency_is_refused_without_force_or_enable(self):
        runner, run = self.fixture(enabled=True)
        with self.assertRaisesRegex(runner.Failure, 'not enabled'):
            runner.install_advanced(run)
        self.assertFalse(any(call[1] == 'enable' or '--force' in call for call in run.calls))
        self.assertEqual(run.attestations, [])

    def test_wrong_pin_is_refused_before_enable(self):
        runner, run = self.fixture(pin='0' * 40)
        with self.assertRaisesRegex(runner.Failure, 'pin'):
            runner.install_advanced(run)
        self.assertFalse(any(call[1] == 'enable' for call in run.calls))
        self.assertEqual(len(run.attestations), 1)

    def test_changed_bytes_extra_files_links_and_specials_are_refused(self):
        for mutation in ('bytes', 'extra', 'link', 'special', 'root-link'):
            with self.subTest(mutation=mutation):
                runner, run = self.fixture(mutation=mutation)
                with self.assertRaises(runner.Failure):
                    runner.install_advanced(run)
                self.assertFalse(any(call[1] == 'enable' or '--force' in call for call in run.calls))
                self.assertEqual(len(run.attestations), 1)

    def test_non_safe_scan_is_refused_before_enable(self):
        for verdict in ('unsafe', 'caution', None):
            with self.subTest(verdict=verdict):
                runner, run = self.fixture(verdict=verdict)
                with self.assertRaisesRegex(runner.Failure, 'safe'):
                    runner.install_advanced(run)
                self.assertFalse(any(call[1] == 'enable' for call in run.calls))
                self.assertEqual(len(run.attestations), 1)

    def test_unrelated_install_failure_never_enters_reuse(self):
        runner, run = self.fixture()
        def failed(*args):
            raise runner.Failure('native install refused for another reason')
        run.hermes = failed
        with self.assertRaisesRegex(runner.Failure, 'another reason'):
            runner.install_advanced(run)
        self.assertEqual(run.attestations, [])
