"""Inert fingerprints must retain decorator source without executing it."""
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router.compat import collect_symbols


class StaticFingerprintTests(unittest.TestCase):
    def test_static_method_fingerprint_matches_loaded_definition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'hqr_static_fixture.py'
            source = 'class Backend:\n    @staticmethod\n    def read(path):\n        return path\n'
            path.write_text(source)
            specs = {'hqr_static_fixture': ('Backend.read',)}
            inert = collect_symbols(directory, specs=specs, constant_specs={})
            module = types.ModuleType('hqr_static_fixture')
            exec(compile(source, str(path), 'exec'), module.__dict__)
            with mock.patch.dict(sys.modules, {'hqr_static_fixture': module}):
                loaded = collect_symbols(directory, specs=specs, constant_specs={})
            self.assertEqual(inert, loaded)


if __name__ == '__main__':
    unittest.main()
