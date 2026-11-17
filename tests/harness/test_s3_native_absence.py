"""Native absent-secret probes never open even a missing credential file."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class AbsentSecretTests(unittest.TestCase):
    def test_native_missing_file_condition_does_not_authorize_a_credential_open(self):
        probe = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as directory:
            try:
                guard = probe.ProbeGuard(directory, missing_credentials=True)
            except TypeError:
                self.fail('guard cannot preserve a native missing-file condition without opening credentials')
            path = Path(directory) / '.env'
            with self.assertRaises(FileNotFoundError):
                guard.audit('open', (str(path), 'r', 0))
            path.mkdir()
            with self.assertRaises(probe.UnsafeProbe):
                guard.audit('open', (str(path), 'r', 0))
            with self.assertRaises(probe.UnsafeProbe):
                guard.audit('open', ('/foreign/.env', 'r', 0))
            self.assertEqual(guard.absent_credentials, ['.env'])
            self.assertEqual(guard.denied, ['open', 'open'])


if __name__ == '__main__':
    unittest.main()
