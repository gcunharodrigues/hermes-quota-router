"""D-43: only a transient collection failure may reuse a previous reading."""
from datetime import timedelta
import unittest

from quota_router import readings
from s2_fakes import NOW, codex


class ReadingQualificationTests(unittest.TestCase):
    def test_same_snapshot_for_timeout_and_incompatible_format(self):
        provider = 'openai-codex'
        good = readings.normalize(provider, codex(10, fetched_at=NOW - timedelta(seconds=10)), NOW, 60)
        incompatible = codex(10)
        raw = incompatible.raw
        assert raw is not None
        raw['rate_limit']['tertiary_window'] = {'used_tokens': 10}
        for fetched, expected in [
            (readings._NativeFailure({'kind': 'timeout'}), ('ok', True, 'timeout')),
            (incompatible, ('unknown', False, 'format_requalification_required')),
        ]:
            with self.subTest(expected=expected):
                found, _ = readings.collect((provider,), NOW, 60, reader=lambda _: fetched,
                                            cache={}, last_good={provider: good})
                actual = found[provider]
                self.assertEqual((actual['state'], bool(actual.get('last_known')),
                                  actual.get('failed_reason', actual['reason'])), expected)
