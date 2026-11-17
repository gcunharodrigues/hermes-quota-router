"""A qualified file-backed host does not qualify another native backend selected through the environment."""
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat


class BackendCompatibilityTests(unittest.TestCase):
    def test_non_file_backend_suspends_even_with_matching_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = types.ModuleType('hermes_cli.config_backend')
            module.__file__ = str(root / 'hermes_cli/config_backend.py')
            package = types.ModuleType('hermes_cli')
            data = root / 'qualified.json'
            data.write_text(json.dumps({'hosts': [{'source_root': str(root), 'label': 'synthetic', 'revision': 'a' * 40,
                                                   'functions': {}, 'constants': {}}]}))
            with mock.patch.dict(sys.modules, {'hermes_cli': package, 'hermes_cli.config_backend': module}), \
                 mock.patch.object(compat, 'DATA', data), \
                 mock.patch.object(compat, 'collect_symbols', return_value={'functions': {}, 'constants': {}}), \
                 mock.patch.dict(os.environ, {'HERMES_CONFIG_BACKEND': 'remote'}):
                result = compat.native_compatibility()
            self.assertFalse(result['ok'])
            self.assertEqual(result['reasons'], ['config_backend_not_file'])


if __name__ == '__main__':
    unittest.main()
