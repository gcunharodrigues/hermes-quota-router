"""A loaded but uninspectable native function cannot borrow a pristine on-disk fingerprint."""
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router.compat import collect_symbols


class SourceTests(unittest.TestCase):
    def test_loaded_source_unavailable_is_not_replaced_with_disk_source(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'synthetic_host.py'
            path.write_text('def operation(value):\n    return value + 1\n')
            loaded = types.ModuleType('synthetic_host')
            loaded.operation = len
            with mock.patch.dict(sys.modules, {'synthetic_host': loaded}):
                found = collect_symbols(root, specs={'synthetic_host': ('operation',)}, constant_specs={})
            self.assertIsNone(found['functions']['synthetic_host.operation'])


if __name__ == '__main__':
    unittest.main()
