"""SOL-02: model format drift is scoped and never disappears into account capacity.

Pure synthetic snapshots; no Engine, native imports, storage or provider requests.
"""
import copy
import unittest

from s2_fakes import NOW, codex, settings
from quota_router.policy import eligibility
from quota_router.readings import normalize

CODEX = 'openai-codex'
TERRA, SOL = 'gpt-6.1-terra', 'gpt-6.1-sol'


class ModelShapeTests(unittest.TestCase):
    def reading(self, rate_limit, model=TERRA):
        snap = codex(10)
        raw = copy.deepcopy(snap.raw)
        raw['additional_rate_limits'] = [{'limit_name': model, 'rate_limit': rate_limit}]
        return normalize(CODEX, type(snap)(snap.provider, snap.source, snap.fetched_at, snap.windows, raw=raw), NOW, 60)

    def test_null_model_limit_requires_requalification_only_for_named_model(self):
        self.check_scoped(self.reading(None))

    def test_new_model_window_slot_requires_requalification_only_for_named_model(self):
        self.check_scoped(self.reading({'tertiary_window': {'used_tokens': 10, 'limit_tokens': 100}}))

    def test_malformed_known_slot_does_not_disappear(self):
        self.check_scoped(self.reading({'primary_window': 'UNQUALIFIED'}))

    def test_unrelated_model_drift_does_not_block_mapped_models(self):
        reading = self.reading(None, 'unrelated-model')
        for model in (TERRA, SOL):
            self.assertEqual(eligibility(reading, settings(), NOW, model=model)['state'], 'free')

    def check_scoped(self, reading):
        self.assertEqual(reading['state'], 'ok')
        verdict = eligibility(reading, settings(), NOW, model=TERRA)
        self.assertEqual((verdict['state'], verdict['blocked_by']), ('unknown', 'model_window_unqualified'))
        self.assertTrue(verdict.get('requalification_required'))
        self.assertEqual(eligibility(reading, settings(), NOW, model=SOL)['state'], 'free')
