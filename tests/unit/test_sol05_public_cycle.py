# decisions/hqr-38-spec.md, SOL-05/D-29: the public cycle must enforce the effective native chain guard.
"""Behavioral public-entry proof, separate from the protected AST wiring test."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from quota_router import groups
from quota_router.apply import Engine
from s3_fakes import Backend, qualified

SOL = {'provider': 'openai-codex', 'model': 'gpt-6.1-sol'}
OPUS = {'provider': 'anthropic', 'model': 'claude-opus-5-5'}


class PublicCycleGuardTests(unittest.TestCase):
    def test_public_cycle_qualifies_legacy_and_refuses_ineligible_without_native_writes(self):
        for eligible in (False, True):
            with self.subTest(eligible=eligible), tempfile.TemporaryDirectory() as root:
                data = Backend()
                data.document['fallback_model'] = copy.deepcopy(SOL if eligible else OPUS)
                before = copy.deepcopy(data.document)
                engine = Engine(root, data, qualified)
                real_guard = groups.effective_fallback_errors
                with mock.patch.object(groups, 'effective_fallback_errors', wraps=real_guard) as guard:
                    engine.cycle({'fallback:conversation': {'chain': [SOL]}}, 100)
                self.assertTrue(guard.called)
                self.assertEqual(data.document['fallback_model'], before['fallback_model'])
                if eligible:
                    self.assertEqual(data.document['fallback_providers'], [SOL])
                    self.assertEqual(len(data.writes), 1)
                    self.assertEqual(engine.state['generation'], 1)
                else:
                    self.assertEqual(data.document, before)
                    self.assertEqual(data.writes, [])
                    self.assertEqual(engine.report(101)['groups_out']['fallback:conversation'], ['fallback_model'])
                    self.assertEqual(engine.state['generation'], 0)
                    self.assertFalse((Path(root) / 'journal.json').exists())
