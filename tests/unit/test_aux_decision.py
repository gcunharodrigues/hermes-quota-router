# Contract: decisions/aux-plan.md, source_decision, D-AUXP-6 and H5e/H6/H7/H8.
"""Pure auxiliary source and task choices over normalized synthetic windows."""
from copy import deepcopy
import unittest

from quota_router import auxiliary
from quota_router.mapping import approved_base, approved_auxiliary
from quota_router.readings import collect
from s2_fakes import NOW, claude, codex, reader_for, settings


class AuxiliaryDecisionTests(unittest.TestCase):
    def found(self, c=30, a=10):
        return collect(('openai-codex', 'anthropic'), NOW, 300,
                       importer=lambda: reader_for(openai_codex=codex(c), anthropic=claude(a)))[0]

    def test_source_uses_approved_conversation_pair_catalog_and_previous_only(self):
        config = settings({'roles': approved_base(), 'conversation.policy': 'pacing'})
        original = deepcopy(config)
        pair = config['roles']['conversation']
        result = auxiliary.source_decision(pair, self.found(c=60), config, NOW, 'anthropic', {})
        self.assertEqual(result['choice'], 'anthropic')
        self.assertEqual(result['tier'], 'subscription')
        self.assertEqual(config, original)
        blocked = auxiliary.source_decision(pair, self.found(), config, NOW, None, {'anthropic': []})
        self.assertEqual(blocked['state'], 'catalog_model_absent')
        self.assertIsNone(blocked['choice'])
        missing = auxiliary.source_decision(None, self.found(), settings(), NOW, None, {})
        self.assertEqual(missing['state'], 'source_map_not_approved')
        self.assertIsNone(missing['choice'])

    def test_task_checks_shared_and_only_returned_qualified_model_windows(self):
        pair = approved_auxiliary()['compression']
        config = settings()
        found = self.found()
        result = auxiliary.task_decision(pair, 'anthropic', found, config, NOW, {})
        self.assertEqual(result['choice'], 'anthropic')
        window = {'kind': 'model_week', 'family': 'sonnet', 'used_pct': 100,
                  'duration_s': 604800, 'reset_at': found['anthropic']['windows'][-1]['reset_at']}
        found['anthropic']['model_windows'] = [window]
        crossed = auxiliary.task_decision(pair, 'anthropic', found, config, NOW, {})
        self.assertEqual(crossed['choice'], 'openai-codex')
        self.assertEqual(crossed['state'], 'crossed_to_other_provider')
        self.assertEqual(crossed['reason'], 'auxiliary_model_not_eligible')
        haiku = auxiliary.task_decision(approved_auxiliary()['title_generation'], 'anthropic', found, config, NOW, {})
        self.assertEqual(haiku['choice'], 'anthropic')
        window['kind'] = 'model_unqualified'
        unknown = auxiliary.task_decision(pair, 'anthropic', found, config, NOW, {})
        self.assertEqual(unknown['model_state']['anthropic'], 'unknown')
        self.assertEqual(unknown['choice'], 'openai-codex')
        exhausted = auxiliary.task_decision(pair, 'anthropic', self.found(100, 100), config, NOW, {})
        self.assertIsNone(exhausted['choice'])
        self.assertTrue(exhausted['resets'])
        absent = auxiliary.task_decision(pair, 'anthropic', self.found(), config, NOW, {'anthropic': []})
        self.assertEqual(absent['state'], 'catalog_model_absent')
        self.assertIsNone(absent['choice'])
