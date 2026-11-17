# Regression contract: decisions/hqr-20-amendment.md, D18 and AC-17; mirror binding and route-only transitions.
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat, groups, routes
from quota_router.render import render
import test_s3_lifecycle as fixtures


class RouteBoundaryTests(unittest.TestCase):
    def test_mirror_cannot_be_qualified_by_updating_native_constant_entries_alone(self):
        host = copy.deepcopy(json.loads(compat.DATA.read_text())['hosts'][0])
        for changed in ('url', 'mode'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                entry = copy.deepcopy(host)
                if changed == 'url':
                    entry['constants']['hermes_cli.auth_constants.DEFAULT_CODEX_BASE_URL'] = 'https://synthetic.invalid/changed'
                else:
                    entry['constants']['hermes_cli.providers.TRANSPORT_TO_API_MODE']['codex_responses'] = 'changed_mode'
                root = Path(directory)
                (root / '.git').mkdir()
                (root / '.git/HEAD').write_text(entry['revision'])
                data = root / 'qualified.json'
                data.write_text(json.dumps({'hosts': [entry]}))
                backend = types.ModuleType('hermes_cli.config_backend')
                backend.__file__ = str(root / 'hermes_cli/config_backend.py')
                constants = types.ModuleType('hermes_constants')
                constants.get_hermes_home = lambda: root
                with mock.patch.dict(sys.modules, {'hermes_cli.config_backend': backend, 'hermes_constants': constants}), \
                     mock.patch.object(compat, 'DATA', data), mock.patch.object(compat, 'collect_symbols', return_value=entry):
                    result = compat._source_compatibility()
                self.assertFalse(result['ok'])
                self.assertIn('native_default_route_mirror', result['reasons'])

    def test_preview_names_wire_sync_even_when_provider_model_and_effort_are_unchanged(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, _, backend = helper.manager(root)
            self.addCleanup(manager.close)
            backend.document['model'].update(provider='anthropic', default='claude-opus-5-5')
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode observe')
            payload = helper.call(manager, 'explain')
            change = payload['decisions']['conversation']['would_change']
            self.assertIsNotNone(change)
            self.assertEqual(change['fields'], ['model.base_url', 'model.api_mode'])
            for command in ('status', 'explain'):
                text = render(command, helper.call(manager, command))
                self.assertIn('sincroniza model.base_url, model.api_mode', text)
            before = backend.read()
            helper.call(manager, 'mode auto')
            self.assertEqual(backend.read()['model']['base_url'], routes.defaults('anthropic')['base_url'])
            helper.call(manager, 'mode off')
            self.assertEqual(backend.read(), before)

    def test_off_then_observe_previews_the_reenrollment_that_auto_will_perform(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, _, backend = helper.manager(root)
            self.addCleanup(manager.close)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode auto')
            backend.document['model']['default'] = 'gpt-6.1-terra'
            helper.call(manager, 'apply')
            helper.call(manager, 'mode off')
            helper.call(manager, 'mode observe')
            observed = helper.call(manager, 'explain')
            self.assertEqual(observed['decisions']['conversation']['state'], 'decided')
            self.assertNotIn('conversation', observed['routing_blocks'])
            self.assertNotIn('conversation fora do Auto', render('explain', observed))
            auto = helper.call(manager, 'mode auto')
            self.assertEqual(auto['decisions']['conversation']['choice'], observed['decisions']['conversation']['choice'])
            self.assertEqual(backend.read()['model']['default'], 'claude-opus-5-5')
