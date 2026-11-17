"""HQR-32 SEC-01: bind scanner subprocess identity, environment and a true absent cwd."""
import importlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class ScannerBindingTests(unittest.TestCase):
    def fixture(self):
        module = importlib.import_module('s3_native_consumers')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / 'plugins/advanced-delegation'
        root.mkdir(parents=True)
        command = ('git', '-c', 'core.fsmonitor=false', '-C', str(root), 'ls-files', '-z', '--', '*.pyc', '*.pyo')
        executable = shutil.which('git', path='/usr/bin:/bin')
        self.assertIsNotNone(executable)
        assert executable is not None
        git = str(Path(executable).resolve())
        return module, module.ProbeGuard(temporary.name), root, command, git

    def test_only_the_qualified_git_executable_can_run_the_admitted_argv(self):
        module, guard, root, command, git = self.fixture()
        with guard.scanner_git(root):
            for executable in ('/usr/bin/true', '/unreviewed/git', sys.executable):
                with self.subTest(executable=executable), self.assertRaises(module.UnsafeProbe):
                    guard.audit('subprocess.Popen', (executable, command, None, None))
            guard.audit('subprocess.Popen', (git, command, None, dict(os.environ)))

    def test_altered_explicit_environment_is_not_the_admitted_environment(self):
        module, guard, root, command, git = self.fixture()
        original = dict(os.environ)
        with guard.scanner_git(root):
            for env in ({}, dict(original, PATH='/unreviewed'), dict(original, GIT_CONFIG_COUNT='1'),
                        dict(original, LD_PRELOAD='/unreviewed.so')):
                with self.subTest(keys=sorted(set(env) - set(original))), self.assertRaises(module.UnsafeProbe):
                    guard.audit('subprocess.Popen', (git, command, None, env))
            guard.audit('subprocess.Popen', (git, command, None, original))

    def test_inherited_environment_drift_is_refused(self):
        module, guard, root, command, git = self.fixture()
        with guard.scanner_git(root):
            with patch.dict(os.environ, {'PATH': '/unreviewed'}):
                with self.assertRaises(module.UnsafeProbe):
                    guard.audit('subprocess.Popen', ('git', command, None, None))
            with patch.dict(os.environ, {'GIT_CONFIG_COUNT': '1'}):
                with self.assertRaises(module.UnsafeProbe):
                    guard.audit('subprocess.Popen', (git, command, None, None))
            guard.audit('subprocess.Popen', (git, command, None, None))

    def test_cwd_text_none_is_not_an_absent_cwd(self):
        module, guard, root, command, git = self.fixture()
        with guard.scanner_git(root):
            with self.assertRaises(module.UnsafeProbe):
                guard.audit('subprocess.Popen', (git, command, 'None', None))
            guard.audit('subprocess.Popen', (git, command, None, None))
