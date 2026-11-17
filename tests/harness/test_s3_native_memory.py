"""SQLite's native memory feature checks do not open a session file."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class MemoryAdmissionTests(unittest.TestCase):
    def test_exact_memory_database_is_safe_but_a_similar_filename_is_not(self):
        module = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as directory:
            guard = module.ProbeGuard(directory)
            try:
                guard.audit('sqlite3.connect', (':memory:',))
            except module.UnsafeProbe:
                self.fail('native SQLite feature checks need an exact in-memory database')
            with self.assertRaises(module.UnsafeProbe):
                guard.audit('sqlite3.connect', (':memory:other',))
            self.assertEqual(guard.denied, ['sqlite3.connect'])


if __name__ == '__main__':
    unittest.main()
