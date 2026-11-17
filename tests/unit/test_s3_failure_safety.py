"""Auto storage failures are redacted and suspend subsequent writes without hiding a pending journal."""
import json
import tempfile
import unittest

import test_s3_lifecycle as fixtures


class FailureSafetyTests(unittest.TestCase):
    def test_unreadable_native_config_returns_redacted_failure_and_latches_suspension(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend = helper.manager(root)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode auto')
            count = len(backend.writes)
            def unreadable():
                raise OSError('SYNTHETIC_PRIVATE_VALUE')
            backend.read = unreadable
            result = helper.call(manager, 'apply')
            self.assertFalse(result['ok'])
            self.assertFalse(result['auto_available'])
            self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', json.dumps(result))
            self.assertEqual(len(backend.writes), count)
            manager.close()


if __name__ == '__main__':
    unittest.main()
