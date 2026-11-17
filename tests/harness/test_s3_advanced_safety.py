"""Regression controls for the exact native-version and metadata admissions."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class AdmissionTests(unittest.TestCase):
    def test_readonly_version_command_requires_exact_argv_and_source_root(self):
        probe = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as home:
            guard = probe.ProbeGuard(home)
            guard.readonly_commands.add((('git', 'rev-parse', 'HEAD'), home))
            guard.audit('subprocess.Popen', ('git', ['git', 'rev-parse', 'HEAD'], home, None))
            for argv, cwd in [(['git', 'rev-parse', 'HEAD'], '/other'), (['git', 'fetch'], home),
                              (['git', 'rev-parse', '--git-dir=/other', 'HEAD'], home)]:
                with self.subTest(argv=argv, cwd=cwd), self.assertRaises(probe.UnsafeProbe):
                    guard.audit('subprocess.Popen', ('git', argv, cwd, None))

    def test_ipv6_capability_check_is_blocked_before_bind_not_allowed(self):
        probe = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as home:
            guard = probe.ProbeGuard(home)
            with self.assertRaises(OSError):
                guard.audit('socket.bind', (object(), ('::1', 0)))
            for address in (('127.0.0.1', 0), ('0.0.0.0', 0), ('127.0.0.1', 80)):
                with self.subTest(address=address), self.assertRaises(probe.UnsafeProbe):
                    guard.audit('socket.bind', (object(), address))

    def test_catalog_url_queries_and_inference_paths_are_never_admitted(self):
        probe = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as home:
            guard = probe.ProbeGuard(home)
            guard.metadata_address = ('127.0.0.1', 31415)
            for url in ('http://127.0.0.1:31415/v1/models?key=synthetic', 'http://127.0.0.1:31415/v1/responses',
                        'https://127.0.0.1:31415/v1/models', 'http://localhost:31415/v1/models'):
                with self.subTest(url=url), self.assertRaises(probe.UnsafeProbe):
                    guard.audit('urllib.Request', (url, None, {}, 'GET'))


if __name__ == '__main__':
    unittest.main()
