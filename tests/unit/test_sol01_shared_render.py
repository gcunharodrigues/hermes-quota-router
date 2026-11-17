"""SOL-01 shared-chain wording, with the renderer's complete decision contract."""
import unittest
from quota_router.render import safety_net_lines

SOL = {'provider': 'openai-codex', 'model': 'gpt-6.1-sol'}
OPUS = {'provider': 'anthropic', 'model': 'claude-opus-5-5'}


class SharedRenderTests(unittest.TestCase):
    def test_complete_decision_explains_native_skip_of_effective_primary(self):
        decisions = {'conversation': {'choice': 'openai-codex', 'safety_net': {'chain': [SOL, OPUS], 'excluded': {}}},
                     'routes': {}, 'cron': {'state': 'follows_conversation'}}
        text = '\n'.join(safety_net_lines(decisions, False))
        self.assertIn('o Hermes tenta Claude', text)
        self.assertNotIn('o Hermes tenta Codex', text)
        self.assertIn('primário efetivo', text)
