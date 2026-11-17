"""SOL-06: null reset means idle only with proved zero usage, scoped to the model."""
from datetime import timedelta
import unittest

from s2_fakes import NOW, WEEK, Snapshot, Window, codex, settings
from quota_router.policy import eligibility
from quota_router.readings import normalize

CODEX, CLAUDE = 'openai-codex', 'anthropic'


class NullResetTests(unittest.TestCase):
    def test_used_account_session_without_reset_is_unknown(self):
        snap = Snapshot(CLAUDE, 'synthetic', NOW, (
            Window('Current session', 50, None), Window('Current week', 30, NOW + timedelta(days=3))))
        verdict = eligibility(normalize(CLAUDE, snap, NOW, 60), settings(), NOW, model='claude-opus-5-5')
        self.assertEqual(verdict['state'], 'unknown')
        self.assertFalse(verdict['credits'])

    def test_used_native_model_week_without_reset_blocks_only_its_family(self):
        snap = Snapshot(CLAUDE, 'synthetic', NOW, (
            Window('Current week', 30, NOW + timedelta(days=3)), Window('Sonnet week', 80, None, scope='model')))
        reading = normalize(CLAUDE, snap, NOW, 60)
        self.assertEqual(reading['state'], 'ok')
        for model, expected in (('claude-sonnet-5-5', 'unknown'), ('claude-opus-5-5', 'free')):
            self.assertEqual(eligibility(reading, settings(), NOW, model=model)['state'], expected)

    def test_used_additional_window_without_reset_blocks_only_its_model(self):
        for seconds in (18000, WEEK):
            with self.subTest(seconds=seconds):
                snap = codex(10)
                raw = dict(snap.raw or {}, additional_rate_limits=[{'limit_name': 'gpt-6.1-terra', 'rate_limit': {
                    'primary_window': {'used_percent': 90, 'limit_window_seconds': seconds, 'reset_at': None}}}])
                reading = normalize(CODEX, Snapshot(CODEX, snap.source, NOW, snap.windows, raw=raw), NOW, 60)
                self.assertEqual(eligibility(reading, settings(), NOW, model='gpt-6.1-terra')['state'], 'unknown')
                self.assertFalse(eligibility(reading, settings(), NOW, model='gpt-6.1-terra')['credits'])
                self.assertEqual(eligibility(reading, settings(), NOW, model='gpt-6.1-sol')['state'], 'free')

    def test_proved_idle_native_windows_keep_capacity_without_fabricated_reset(self):
        snap = Snapshot(CLAUDE, 'synthetic', NOW, (
            Window('Current session', 0, None), Window('Current week', 0, None), Window('Sonnet week', 0, None, scope='model')))
        reading = normalize(CLAUDE, snap, NOW, 60)
        for model in ('claude-opus-5-5', 'claude-sonnet-5-5'):
            verdict = eligibility(reading, settings(), NOW, model=model)
            self.assertEqual((verdict['state'], verdict['score'], verdict['resets']), ('free', 1.0, []))
        self.assertTrue(all(w['reset_at'] is None for w in reading['windows']))
