"""D-43: the native reader must not turn an unclassified failure into evidence."""
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from quota_router import readings
from s2_fakes import NOW, codex


class AmbiguousReadingTests(unittest.TestCase):
    def test_native_missing_snapshot_or_unclassified_callback_never_reuses_quota(self):
        provider = 'openai-codex'
        good = readings.normalize(provider, codex(10), NOW, 60)
        native = ModuleType('agent.account_usage')

        def without_callback(provider, *, read_only):
            return None

        def unclassified_callback(provider, *, read_only, on_error):
            on_error({'kind': 'error'})
            return None

        for fetch, reason in ((without_callback, 'no_snapshot'), (unclassified_callback, 'reader_error')):
            with self.subTest(reason=reason), patch.dict(sys.modules, {'agent.account_usage': native}):
                setattr(native, 'fetch_account_usage', fetch)
                found, _ = readings.collect((provider,), NOW, 60, cache={}, last_good={provider: good})
                self.assertEqual((found[provider]['state'], found[provider]['reason']), ('unknown', reason))
                self.assertFalse(found[provider].get('last_known'))
