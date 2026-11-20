"""SOL-01: a shared chain must serve pinned primaries that differ from Auto.

Generated chain only; native refresh and skip are separately exercised from read-only host source.
"""
import unittest

from s2_fakes import CREDITS_OK, NOW, claude, codex, settings
from quota_router.mapping import approved_base
from quota_router.policy import decide, fallback_chain
from quota_router.readings import normalize

CODEX, CLAUDE = 'openai-codex', 'anthropic'
SOL = {'provider': CODEX, 'model': 'gpt-6.2-sol'}
OPUS = {'provider': CLAUDE, 'model': 'claude-opus-5-5'}
PAIR = approved_base()['conversation']


class PinnedChainTests(unittest.TestCase):
    def decision(self, c, a, overrides=None):
        readings = {CODEX: normalize(CODEX, c, NOW, 60), CLAUDE: normalize(CLAUDE, a, NOW, 60)}
        return decide('conversation', readings, settings(overrides), NOW, models={p: row['model'] for p, row in PAIR.items()})

    def test_pinned_sol_still_has_opus_after_auto_moves_to_opus(self):
        for c in (codex(10, session_used=96), codex(10, session_used=100), None):
            with self.subTest(c=c):
                decision = self.decision(c, claude(30))
                self.assertEqual(decision['choice'], CLAUDE)
                self.assertIn(OPUS, fallback_chain(decision, PAIR)['chain'])

    def test_all_eligible_candidates_serve_either_pinned_primary_across_pair_matrix(self):
        stages = (50, 97, 100)
        for codex_used in stages:
            for claude_used in stages:
                with self.subTest(codex=codex_used, claude=claude_used):
                    decision = self.decision(codex(20, session_used=codex_used), claude(40, session_used=claude_used))
                    net = fallback_chain(decision, PAIR)
                    expected = [row for used, row in ((codex_used, SOL), (claude_used, OPUS)) if used < 100]
                    if not expected:
                        self.assertIsNone(net)  # D-30: no decision means no configuration write, not an empty-chain promise.
                    else:
                        self.assertCountEqual(net['chain'], expected)
                        for primary in (SOL, OPUS):
                            peers = [row for row in net['chain'] if row != primary]
                            self.assertEqual(OPUS in peers, claude_used < 100 and primary != OPUS)
                            self.assertEqual(SOL in peers, codex_used < 100 and primary != SOL)

    def test_auto_on_either_side_is_itself_available_to_opposite_pinned_chat(self):
        for principal in (CODEX, CLAUDE):
            with self.subTest(principal=principal):
                decision = self.decision(codex(10), claude(20), {'principal': principal})
                self.assertEqual(decision['choice'], principal)
                self.assertEqual(fallback_chain(decision, PAIR)['chain'][0]['provider'], principal)
                self.assertCountEqual(fallback_chain(decision, PAIR)['chain'], [SOL, OPUS])

    def test_free_precedes_pressured_and_credits_are_last(self):
        decision = self.decision(codex(100, credits=CREDITS_OK), claude(20, session_used=97))
        self.assertEqual(fallback_chain(decision, PAIR)['chain'], [OPUS, SOL])
        no_paid = self.decision(codex(100, credits=CREDITS_OK), claude(20), {'credits.openai-codex': False})
        self.assertEqual(fallback_chain(no_paid, PAIR)['chain'], [OPUS])
