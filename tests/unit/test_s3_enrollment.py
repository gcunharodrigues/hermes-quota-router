"""Regression contracts for enrollment without candidates and group-local recovery exclusion."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from quota_router.apply import Engine, durable
from quota_router.groups import target
from s3_fakes import Backend, TARGET, qualified


class EnrollmentTests(unittest.TestCase):
    def test_no_candidate_still_captures_baseline_of_enabled_groups(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            engine = Engine(root, backend, compatible=qualified)
            engine.cycle({}, enabled={'conversation', 'general'}, now=100)
            state = json.loads((Path(root) / 'state.json').read_text())
            self.assertEqual(set(state['groups']), {'conversation', 'general'})
            self.assertEqual(backend.writes, [])
            self.assertTrue(state['auto_declared'])

    def test_external_third_value_excludes_only_affected_group(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            engine = Engine(root, backend, compatible=qualified)
            engine.cycle({'conversation': TARGET, 'general': TARGET}, now=100)
            state = json.loads((Path(root) / 'state.json').read_text())
            entry = state['groups']['conversation']
            durable(Path(root) / 'journal.json', {'group': 'conversation', 'prior': entry['baseline'], 'target': entry['last'],
                                                 'at': 200, 'restore': False})
            backend.document['model']['default'] = 'gpt-6.1-terra'
            engine.restore(now=300)
            route = backend.document['delegation']['backends']['model_map']['options'][0]
            self.assertEqual(route['provider'], 'openai-codex')
            self.assertEqual(backend.document['model']['default'], 'gpt-6.1-terra')
            self.assertIn('conversation', engine.report(301)['groups_out'])

    def test_disallowed_persisted_projection_suspends_without_echo_or_write(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            engine = Engine(root, backend, compatible=qualified)
            engine.cycle({'conversation': TARGET}, now=100)
            file = Path(root) / 'state.json'
            state = json.loads(file.read_text())
            state['groups']['conversation']['baseline']['model.api_key'] = {'present': True, 'value': 'SYNTHETIC_PRIVATE_VALUE'}
            durable(file, state)
            before = backend.read()
            reloaded = Engine(root, backend, compatible=qualified)
            with self.assertRaises(ValueError):
                reloaded.restore(now=200)
            self.assertEqual(backend.document, before)
            self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', repr(reloaded.report(201)))


if __name__ == '__main__':
    unittest.main()
