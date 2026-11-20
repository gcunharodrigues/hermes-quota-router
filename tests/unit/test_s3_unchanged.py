"""An unchanged but enrolled decision still has a durable generation, not an invented application."""
import json
from pathlib import Path
import tempfile
import unittest

from quota_router.apply import Engine
from s3_fakes import Backend, qualified


class UnchangedDecisionTests(unittest.TestCase):
    def test_first_unchanged_decision_is_committed_once_without_native_writes(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            # D18: unchanged includes the native route fields, not only provider/model/effort.
            backend.document["model"].update(base_url="https://chatgpt.com/backend-api/codex", api_mode="codex_responses")
            engine = Engine(root, backend, compatible=qualified)
            selection = {'provider': 'openai-codex', 'model': 'gpt-6.2-sol', 'effort': 'high'}
            engine.cycle({'conversation': selection}, now=100)
            first = engine.report(200)
            self.assertEqual(first['generation'], 1)
            self.assertEqual(first['age_s'], 100)
            self.assertEqual(backend.writes, [])
            engine.cycle({'conversation': selection}, now=300)
            self.assertEqual(engine.report(400)['generation'], 1)
            self.assertFalse((Path(root) / 'journal.json').exists())


if __name__ == '__main__':
    unittest.main()
