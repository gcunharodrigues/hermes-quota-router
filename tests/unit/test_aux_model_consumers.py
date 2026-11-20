# Contract: decisions/aux-plan.md, H8a/H8b/H11/H16 and decision-time revalidation under AUXP-04.
"""Additional synthetic consumer verification; no provider window is inferred from a missing field."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

import test_aux_lifecycle as fixtures
from quota_router.mapping import approved_auxiliary
from s2_fakes import NOW, Window, claude, codex


class AuxiliaryModelConsumerTests(unittest.TestCase):
    def manager(self, root, **kwargs):
        fixture = fixtures.AuxiliaryLifecycleTests()
        self.addCleanup(fixture.doCleanups)
        return fixture.manager(root, **kwargs)

    def call(self, manager, command):
        return json.loads(manager.command(command + ' --json'))

    def test_returned_sonnet_window_crosses_only_sonnet_tasks_and_removal_uses_shared_windows(self):
        for starts_claude in (False, True):
            with self.subTest(starts_claude=starts_claude), tempfile.TemporaryDirectory() as root:
                m, _, b, snapshots = self.manager(root)
                if starts_claude:
                    self.assertTrue(self.call(m, 'mode auto')['ok'])
                snapshots['openai_codex'] = codex(60, week_reset_h=120)
                native = claude(10)
                snapshots['anthropic'] = replace(native, windows=native.windows + (
                    Window('Sonnet week', 100, NOW + timedelta(hours=120), scope='model'),))
                m.cache.clear()
                result = self.call(m, 'status' if starts_claude else 'mode auto')
                self.assertTrue(result['ok'], result)
                self.assertEqual(result['decisions']['auxiliary']['source']['choice'], 'anthropic')
                self.assertEqual(b.read()['auxiliary']['title_generation']['provider'], 'anthropic')
                self.assertEqual(b.read()['auxiliary']['compression']['provider'], 'openai-codex')
                self.assertEqual(result['decisions']['auxiliary']['tasks']['compression']['state'], 'crossed_to_other_provider')
                snapshots['anthropic'] = claude(10)
                m.cache.clear()
                self.assertTrue(self.call(m, 'status')['ok'])
                self.assertEqual(b.read()['auxiliary']['compression']['provider'], 'anthropic')

    def test_plugin_collision_is_not_written_and_inheriting_child_is_only_reported(self):
        with tempfile.TemporaryDirectory() as root:
            registry = {'ok': True, 'tasks': {'approval': {}, 'child_task': {'inherit_from': 'compression'}}}
            m, _, b, _ = self.manager(root, auxiliary_registry=lambda: registry)
            before = b.read()['auxiliary']['approval']
            result = self.call(m, 'mode auto')
            self.assertTrue(result['ok'], result)
            self.assertEqual(b.read()['auxiliary']['approval'], before)
            self.assertNotIn('child_task', b.read()['auxiliary'])
            self.assertEqual(result['coverage']['auxiliary']['inherited'], {'child_task': 'compression'})
            text = m.command('explain')
            self.assertIn('child_task segue compression', text)
            self.assertNotIn('aux:', text)
            self.assertNotIn('plugin_task_collision', text)

    def test_outside_map_auto_image_and_sensitive_options_are_untouched_without_value_leak(self):
        with tempfile.TemporaryDirectory() as root:
            m, _, b, _ = self.manager(root)
            b.document['auxiliary']['approval']['provider'] = 'auto'
            b.document['auxiliary']['compression']['model'] = 'gpt-manual-model'
            b.document['auxiliary']['monitor']['api_key'] = 'SYNTHETIC_PRIVATE_SECRET'
            b.document['auxiliary']['unmapped'] = {'provider': 'openai-codex', 'model': 'gpt-6-luna'}
            before = b.read()
            result = self.call(m, 'mode auto')
            self.assertTrue(result['ok'], result)
            for task in ('approval', 'compression', 'monitor', 'unmapped'):
                self.assertEqual(b.read()['auxiliary'][task], before['auxiliary'][task])
            self.assertEqual(b.read()['image_gen'], before['image_gen'])
            self.assertNotIn('SYNTHETIC_PRIVATE_SECRET', json.dumps(result))
            state = ''.join(path.read_text() for path in Path(root).glob('*.json'))
            self.assertNotIn('SYNTHETIC_PRIVATE_SECRET', state)
            self.assertEqual(result['decisions']['auxiliary']['tasks']['monitor']['blocked_fields'], ['auxiliary.monitor.api_key'])

    def test_paired_decision_revalidates_readings_that_expire_after_preview(self):
        with tempfile.TemporaryDirectory() as root:
            m, _, b, _ = self.manager(root)
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            before, count = b.read(), len(b.writes)
            original = m.decisions
            def advance(*args, **kwargs):
                result = original(*args, **kwargs)
                if m.engine._directory_fd is None:
                    m.clock = lambda: NOW + timedelta(seconds=61)
                return result
            m.decisions = advance
            m.cache.clear()
            result = self.call(m, 'status')
            self.assertTrue(result['ok'], result)
            source = result['decisions']['auxiliary']['source']
            self.assertIsNone(source['choice'])
            self.assertEqual(source['states'], {'openai-codex': 'unknown', 'anthropic': 'unknown'})
            del before['fallback_providers']
            options = before['delegation']['backends']['model_map']['options']
            del next(option for option in options if option['name'] == 'general')['fallback_providers']
            self.assertEqual(b.read(), before)
            self.assertCountEqual(b.writes[count:], [({}, ('fallback_providers',)),
                                                     ({'delegation.backends.model_map.options': options}, ())])
