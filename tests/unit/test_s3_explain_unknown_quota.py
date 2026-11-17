# Regression contract: README.md HQR-34; decisions/hqr-20-amendment.md AC-16/24.
"""Synthetic quota gaps must not imply that a valid approved map was replaced by defaults."""
import copy
import json
import tempfile
import unittest

from quota_router.lifecycle import Management
from quota_router.mapping import approved_base
from quota_router.render import render
from s2_fakes import codex, reader_for
from s3_fakes import Backend, qualified
import test_s2_commands as fixtures


class ExplainUnknownQuotaTests(unittest.TestCase):
    def test_unknown_provider_keeps_valid_approved_map_without_claiming_defaults(self):
        roles = copy.deepcopy(approved_base())
        roles['general']['anthropic']['effort'] = 'low'
        ctx = fixtures.Context({'mode': 'observe', 'roles': roles})
        reader = reader_for(openai_codex=codex(10), anthropic=None)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        backend = Backend()
        options = backend.document['delegation']['backends']['model_map']['options']
        backend.document['delegation']['backends']['model_map']['options'] = [o for o in options if o['name'] == 'general']
        clock = fixtures.Clock()
        manager = Management(ctx, importer=lambda: reader, sources=lambda: (backend.read(), []), clock=clock,
                             profile=lambda: 'default', backend=backend, data_dir=directory.name, compatible=qualified)
        self.addCleanup(manager.close)
        before = backend.read()
        payload = json.loads(manager.command('explain --json'))
        self.assertTrue(payload['decision_incomplete'])
        self.assertFalse(payload['settings_invalid'])
        self.assertEqual(payload['quota']['providers']['anthropic']['state'], 'unknown')
        self.assertEqual(payload['map']['status'], 'approved')
        self.assertEqual(payload['map']['source'], 'settings.roles')
        self.assertEqual(payload['map']['variants']['base']['general']['anthropic']['effort'], 'low')
        self.assertEqual(payload['routing_blocks'], {})
        text = render('explain', payload)
        self.assertIn('Decisão incompleta', text)
        self.assertIn('Claude claude-opus-5-5 low', text)
        self.assertNotIn('a explicação usa os padrões', text)
        self.assertEqual(ctx.writes, [])
        self.assertEqual(backend.read(), before)
        self.assertEqual(backend.writes, [])


if __name__ == '__main__':
    unittest.main()
