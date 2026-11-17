"""Native decorators and SQLite URIs must not bypass source or I/O admission."""
from contextlib import contextmanager
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


@contextmanager
def native_scope_fixture():
    yield 'native body'


class BoundaryContracts(unittest.TestCase):
    def test_native_contextmanager_is_verified_at_its_wrapped_source(self):
        probe = importlib.import_module('s3_native_consumers')
        host = probe.NativeHost.__new__(probe.NativeHost)
        host.root = Path(__file__).resolve().parent
        host.sources = {}
        try:
            function = host.function(__name__, 'native_scope_fixture')
        except probe.ProbeFailure as exc:
            self.fail(str(exc))
        with function() as result:
            self.assertEqual(result, 'native body')
        self.assertEqual(host.sources[__name__ + '.native_scope_fixture']['file'], Path(__file__).name)

    def test_sqlite_read_uri_is_admitted_only_inside_disposable_home(self):
        probe = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as directory:
            guard = probe.ProbeGuard(directory)
            guard.audit('sqlite3.connect', ('file:' + directory + '/probe.db?mode=ro',))
            self.assertEqual(guard.denied, [])
            for uri in ('file:/foreign/state.db?mode=ro', 'file:' + directory + '/../foreign.db?mode=ro',
                        'file://remote' + directory + '/probe.db?mode=ro'):
                with self.subTest(uri=uri), self.assertRaises(probe.UnsafeProbe):
                    guard.audit('sqlite3.connect', (uri,))

    def test_complete_gate_refuses_forbidden_attempt_even_with_all_scenarios_true(self):
        probe = importlib.import_module('s3_native_consumers')
        report = {'scenarios': {n: {'pass': True} for n in probe.REQUIRED}, 'audit_denied': ['socket.connect']}
        with self.assertRaises(probe.ProbeFailure):
            probe.require_complete(report)


if __name__ == '__main__':
    unittest.main()
