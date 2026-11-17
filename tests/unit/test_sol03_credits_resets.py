"""SOL-03: A23 is temporal only; cached model resets are not current capacity."""
import copy
from datetime import timedelta
import unittest

from s2_fakes import CREDITS_OK, NOW, Snapshot, Window, WEEK, claude, codex, settings
from quota_router.policy import decide, eligibility
from quota_router.readings import collect, normalize, revalidate

CODEX, CLAUDE = 'openai-codex', 'anthropic'
TERRA, SOL = 'gpt-6.1-terra', 'gpt-6.1-sol'


def limited(seconds=WEEK, reset=NOW + timedelta(seconds=1)):
    snap = codex(10, credits=CREDITS_OK)
    raw = dict(snap.raw or {}, additional_rate_limits=[{'limit_name': TERRA, 'rate_limit': {
        'primary_window': {'used_percent': 10, 'limit_window_seconds': seconds, 'reset_at': reset.isoformat()}}}])
    return Snapshot(CODEX, snap.source, NOW, snap.windows, raw=raw)


class CreditAndResetTests(unittest.TestCase):
    def test_model_format_drift_does_not_authorize_credits(self):
        reading = normalize(CODEX, limited(seconds=86400), NOW, 60)
        verdict = eligibility(reading, settings(), NOW, model=TERRA)
        self.assertEqual(verdict['state'], 'unknown')
        self.assertFalse(verdict['credits'])
        found = {CODEX: reading, CLAUDE: normalize(CLAUDE, claude(100), NOW, 60)}
        self.assertIsNone(decide('routine', found, settings(), NOW, models={CODEX: TERRA})['choice'])

    def test_format_drift_outranks_temporal_exception_regardless_of_order(self):
        reading = normalize(CODEX, limited(seconds=86400), NOW, 60)
        reading['windows'][0]['reset_at'] = (NOW + timedelta(days=8)).isoformat()
        for windows, extra in ((reading['windows'], reading['model_windows']), (reading['model_windows'], reading['windows'])):
            verdict = eligibility(dict(reading, windows=windows, model_windows=extra), settings(), NOW, model=TERRA)
            self.assertEqual(verdict['blocked_by'], 'model_window_unqualified')
            self.assertFalse(verdict['credits'])

    def test_temporal_a23_exception_keeps_verified_credits(self):
        snap = codex(100, week_reset_h=192, credits=CREDITS_OK)
        verdict = eligibility(normalize(CODEX, snap, NOW, 60), settings(), NOW, model=TERRA)
        self.assertEqual((verdict['state'], verdict['blocked_by'], verdict['credits']), ('unknown', 'inconsistent_window', True))

    def test_collect_refetches_when_only_model_reset_crossed(self):
        cache = {}
        collect((CODEX,), NOW, 60, reader=lambda _: limited(), cache=cache)
        later = NOW + timedelta(seconds=2)
        fresh = limited(reset=later + timedelta(days=3))
        fresh = Snapshot(CODEX, fresh.source, later, fresh.windows, raw=fresh.raw)
        found, queries = collect((CODEX,), later, 60, reader=lambda _: fresh, cache=cache)
        self.assertEqual(queries, 1)
        self.assertEqual(eligibility(found[CODEX], settings(), later, model=TERRA)['state'], 'free')
        self.assertEqual(found[CODEX]['fetched_at'], later.isoformat())

    def test_final_time_model_reset_blocks_only_affected_model_without_credits(self):
        reading = normalize(CODEX, limited(), NOW, 60)
        before = copy.deepcopy(reading)
        later = NOW + timedelta(seconds=2)
        checked = revalidate({CODEX: reading}, later, 60)[CODEX]
        terra = eligibility(checked, settings(), later, model=TERRA)
        self.assertEqual(terra['state'], 'unknown')
        self.assertFalse(terra['credits'])
        self.assertEqual(eligibility(checked, settings(), later, model=SOL)['state'], 'free')
        self.assertEqual(reading, before)

    def test_elapsed_window_is_not_temporal_credit_exception(self):
        reading = normalize(CODEX, limited(), NOW, 60)
        verdict = eligibility(reading, settings(), NOW + timedelta(seconds=2), model=TERRA)
        self.assertEqual(verdict['state'], 'unknown')
        self.assertFalse(verdict['credits'])
