"""Fingerprints detect body and constant drift, not just signature drift."""
import importlib.util
import unittest


def original(value):
    return value + 1


def changed(value):
    return value + 2


class CompatibilityTests(unittest.TestCase):
    def check_api(self):
        self.assertIsNotNone(importlib.util.find_spec('quota_router.compat'), 'S3 fingerprints are missing')
        from quota_router.compat import fingerprint, verify
        return fingerprint, verify

    def test_body_changed_without_signature_change_suspends(self):
        fingerprint, verify = self.check_api()
        expected = {'functions': {'host.fn': fingerprint(original)}, 'constants': {'host.FOLLOW': ['model']}}
        good = verify(expected, {'host.fn': original}, {'host.FOLLOW': ['model']})
        self.assertTrue(good['ok'])
        bad = verify(expected, {'host.fn': changed}, {'host.FOLLOW': ['model']})
        self.assertFalse(bad['ok'])
        self.assertEqual(bad['reasons'], ['host.fn'])

    def test_constant_changed_and_source_unavailable_suspend(self):
        fingerprint, verify = self.check_api()
        expected = {'functions': {'host.fn': fingerprint(original)}, 'constants': {'host.FOLLOW': ['model']}}
        self.assertEqual(verify(expected, {'host.fn': original}, {'host.FOLLOW': ['model', 'delegation']})['reasons'], ['host.FOLLOW'])
        self.assertEqual(verify(expected, {'host.fn': len}, {'host.FOLLOW': ['model']})['reasons'], ['host.fn'])


if __name__ == '__main__':
    unittest.main()
