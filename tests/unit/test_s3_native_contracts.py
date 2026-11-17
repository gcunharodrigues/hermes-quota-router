"""Native hook error shape, explicit re-enrollment and retained absence records."""
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from s2_fakes import NOW
from s3_fakes import Backend, TARGET, qualified
from quota_router.apply import Engine
from quota_router.lifecycle import Management
import test_s3_lifecycle as fixtures


class NativeContractsTests(unittest.TestCase):
    def test_native_error_dict_records_class_only(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, _ = helper.manager(root)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode auto')
            ctx.hooks['api_request_error'](provider='anthropic', model='claude-opus-5-5',
                error={'type': 'RateLimitError', 'message': 'SYNTHETIC_PRIVATE_MESSAGE'}, request={'body': 'SYNTHETIC_PRIVATE_BODY'})
            manager.wait_hooks()
            events = json.loads((Path(root) / 'events.json').read_text())
            self.assertEqual(events[-1]['error_class'], 'RateLimitError')
            self.assertNotIn('SYNTHETIC_PRIVATE', repr(events))
            manager.close()

    def test_explicit_off_auto_reenrolls_previously_divergent_group(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend = helper.manager(root)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode auto')
            backend.document['model']['default'] = 'gpt-6.1-terra'
            helper.call(manager, 'apply')
            helper.call(manager, 'mode off')
            helper.call(manager, 'mode auto')
            self.assertEqual(backend.document['model']['default'], 'claude-opus-5-5')
            helper.call(manager, 'mode off')
            self.assertEqual(backend.document['model']['default'], 'gpt-6.1-terra')

    def test_auto_marker_survives_missing_subtree_and_is_reported_while_off(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend = helper.manager(root)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode auto')
            manager.close()
            fresh = fixtures.AutoContext()
            reloaded = Management(fresh, importer=lambda: None, sources=lambda: (backend.read(), []),
                clock=lambda: NOW + timedelta(hours=1), profile=lambda: 'default', backend=backend, data_dir=root, compatible=qualified)
            result = helper.call(reloaded, 'status')
            self.assertEqual(result['mode_effective'], 'off')
            self.assertIn('applied', result)
            self.assertIsNotNone(result['applied']['absence'])
            self.assertIn('plugin ausente', reloaded.command('status'))
            self.assertEqual(fresh.registrations, [])


if __name__ == '__main__':
    unittest.main()
