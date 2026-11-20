"""D-43: a retained reading cannot authorize a paid candidate."""
import unittest

from quota_router.policy import decide, fallback_chain
from quota_router.readings import normalize
from quota_router.settings import DEFAULTS
from s2_fakes import NOW, claude, codex
from test_hqr38_readings import CREDITS_OK


class PaidEvidenceTests(unittest.TestCase):
    def test_carried_balance_does_not_authorize_primary_or_fallback(self):
        a, b = 'openai-codex', 'anthropic'
        settings = dict(DEFAULTS, **{'credits.openai-codex': True})
        paid = normalize(a, codex(100, credits=CREDITS_OK), NOW, 60)
        exhausted = normalize(b, claude(100), NOW, 60)
        self.assertEqual(decide('general', {a: paid, b: exhausted}, settings, NOW)['tier'], 'credits')
        carried = dict(paid, last_known=True)
        self.assertIsNone(decide('general', {a: carried, b: exhausted}, settings, NOW)['choice'])
        free = normalize(b, claude(10), NOW, 60)
        result = decide('general', {a: carried, b: free}, settings, NOW)
        pair = {a: {'model': 'codex'}, b: {'model': 'claude'}}
        chain = fallback_chain(result, pair)
        assert chain is not None
        self.assertEqual(chain['chain'], [{'provider': b, 'model': 'claude'}])
