"""Observe preferences must survive Auto enrollment without masking external changes."""
import tempfile
import unittest

from quota_router import groups
from s2_fakes import claude, codex, reader_for
import test_s3_lifecycle as lifecycle_fixtures


class ModeContinuityTests(unittest.TestCase):
    def test_auto_applies_the_observed_preference_below_hysteresis(self):
        helper = lifecycle_fixtures.AutoCommandTests()
        for policy in ('principal_first', 'pacing'):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as root:
                manager, ctx, backend = helper.manager(root, lifecycle_fixtures.AutoContext({'conversation.policy': policy}))
                self.addCleanup(manager.close)
                snapshots = {'openai_codex': codex(30, week_reset_h=84), 'anthropic': claude(10, week_reset_h=84)}
                manager.importer = lambda: reader_for(**snapshots)
                baseline = backend.read()
                self.assertTrue(helper.call(manager, 'config approve-map base')['ok'])
                self.assertTrue(helper.call(manager, 'mode observe')['ok'])
                snapshots['openai_codex'] = codex(5, week_reset_h=84)
                manager.cache.clear()
                observed = helper.call(manager, 'explain')['decisions']
                general = observed['routes']['general']
                self.assertEqual((general['choice'], general['reason']), ('anthropic', 'previous_preference_kept'))
                self.assertEqual(backend.read(), baseline)
                self.assertEqual(backend.writes, [])
                auto = helper.call(manager, 'mode auto')
                self.assertTrue(auto['ok'], auto)
                self.assertEqual(auto['decisions']['routes']['general']['choice'], general['choice'])
                selections = {'general': general, 'conversation': observed['conversation']}
                for role, decision in selections.items():
                    target = dict(ctx.settings['roles'][role][decision['choice']], provider=decision['choice'])
                    self.assertEqual(groups.project(backend.read(), role), groups.target(role, target))
                count = len(backend.writes)
                for _ in range(3):
                    manager.cache.clear()
                    self.assertEqual(helper.call(manager, 'apply')['decisions']['routes']['general']['choice'], general['choice'])
                self.assertEqual(len(backend.writes), count)
                self.assertTrue(helper.call(manager, 'mode off')['ok'])
                self.assertEqual(backend.read(), baseline)

    def test_changed_route_or_settings_does_not_inherit_an_observed_preference(self):
        helper = lifecycle_fixtures.AutoCommandTests()
        for changed in ('route', 'settings'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as root:
                manager, ctx, backend = helper.manager(root)
                self.addCleanup(manager.close)
                snapshots = {'openai_codex': codex(30, week_reset_h=84), 'anthropic': claude(10, week_reset_h=84)}
                manager.importer = lambda: reader_for(**snapshots)
                helper.call(manager, 'config approve-map base')
                helper.call(manager, 'mode observe')
                snapshots['openai_codex'] = codex(5, week_reset_h=84)
                manager.cache.clear()
                self.assertEqual(helper.call(manager, 'explain')['decisions']['routes']['general']['choice'], 'anthropic')
                if changed == 'route':
                    backend.document['delegation']['backends']['model_map']['options'][0]['model'] = 'gpt-6.1-terra'
                else:
                    ctx.settings['limits.reading_max_age_s'] = 61
                auto = helper.call(manager, 'mode auto')
                self.assertTrue(auto['ok'], auto)
                self.assertEqual(auto['decisions']['routes']['general']['choice'], 'openai-codex')
                self.assertEqual(backend.read()['delegation']['backends']['model_map']['options'][0]['provider'], 'openai-codex')

    def test_external_edit_after_confirmed_auto_write_resets_preference_without_overwrite(self):
        helper = lifecycle_fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend = helper.manager(root)
            self.addCleanup(manager.close)
            snapshots = {'openai_codex': codex(30, week_reset_h=84), 'anthropic': claude(10, week_reset_h=84)}
            manager.importer = lambda: reader_for(**snapshots)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode observe')
            helper.call(manager, 'mode auto')
            snapshots['openai_codex'] = codex(5, week_reset_h=84)
            manager.cache.clear()
            self.assertEqual(helper.call(manager, 'explain')['decisions']['routes']['general']['choice'], 'anthropic')
            backend.document['delegation']['backends']['model_map']['options'][0]['model'] = 'claude-sonnet-5-5'
            before, count = backend.read(), len(backend.writes)
            result = helper.call(manager, 'explain')
            self.assertIsNone(result['decisions']['routes']['general']['choice'])
            self.assertEqual(result['decisions']['routes']['general']['state'], 'group_blocked')
            self.assertFalse(any(key[0] == 'general' for key in manager.preferences))
            self.assertIn('general', result['applied']['groups_out'])
            self.assertEqual(backend.read(), before)
            self.assertEqual(len(backend.writes), count)
