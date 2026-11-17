"""Applied status distinguishes every enrolled role and its actual persisted target from a recommendation."""
import tempfile
import unittest

import test_s3_lifecycle as fixtures


class AppliedStatusTests(unittest.TestCase):
    def test_each_role_exposes_last_applied_values_and_human_model(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend = helper.manager(root)
            helper.call(manager, 'config approve-map base')
            result = helper.call(manager, 'mode auto')
            groups = result['applied'].get('groups', {})
            self.assertEqual(set(groups), {'conversation', 'general'})
            self.assertEqual(groups['conversation']['values']['model.default']['value'], 'claude-opus-5-5')
            self.assertEqual(groups['general']['values']['provider']['value'], 'anthropic')
            self.assertIn('claude-opus-5-5', manager.command('status'))
            manager.close()


if __name__ == '__main__':
    unittest.main()
