# Regression contract: decisions/hqr-20-amendment.md, D18 and D9: render the effective S3 map and measured qualification.
import copy
import tempfile
import unittest

from quota_router.mapping import approved_base
from quota_router.render import render
import test_s3_lifecycle as fixtures


class EffectiveExplainTests(unittest.TestCase):
    def test_explain_shows_every_approved_s3_cell_and_no_separate_cron_row(self):
        helper = fixtures.AutoCommandTests()
        for mode in ('observe', 'auto'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as root:
                manager, ctx, _ = helper.manager(root)
                self.addCleanup(manager.close)
                helper.call(manager, 'config approve-map base')
                helper.call(manager, 'mode ' + mode)
                payload = helper.call(manager, 'explain')
                expected = approved_base()
                expected.pop('cron')
                self.assertEqual(payload['map']['status'], 'approved')
                self.assertEqual(payload['map']['variants']['base'], expected)
                self.assertEqual(payload['map']['cron'], {'follows': 'conversation'})
                text = render('explain', payload)
                for role, pair in expected.items():
                    self.assertIn('• ' + role + ': Codex ' + pair['openai-codex']['model'] + ' ' + pair['openai-codex']['effort'] +
                                  ' · Claude ' + pair['anthropic']['model'] + ' ' + pair['anthropic']['effort'], text)
                self.assertNotIn('• cron:', text)
                self.assertNotIn('Aprove uma variante', text)

    def test_edited_or_partial_approved_map_is_rendered_from_settings_not_a_second_table(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, _ = helper.manager(root)
            self.addCleanup(manager.close)
            helper.call(manager, 'config approve-map base')
            ctx.settings['roles'] = copy.deepcopy(ctx.settings['roles'])
            ctx.settings['roles']['general']['anthropic']['effort'] = 'low'
            ctx.settings['roles'].pop('routine')
            helper.call(manager, 'mode observe')
            payload = helper.call(manager, 'explain')
            expected = {r: pair for r, pair in ctx.settings['roles'].items() if r != 'cron'}
            self.assertEqual(payload['map']['variants']['base'], expected)
            self.assertIn('Claude claude-opus-5-5 low', render('explain', payload))
            self.assertNotIn('routine', payload['map']['variants']['base'])

    def test_json_reports_real_native_qualification_without_claiming_installed_smoke(self):
        helper = fixtures.AutoCommandTests()
        revision = 'a' * 40
        for has_map in (False, True):
            for revisionless in (False, True):
                with self.subTest(has_map=has_map, revisionless=revisionless), tempfile.TemporaryDirectory() as root:
                    checked = {'ok': True, 'reasons': [], 'host': 'qualified native source',
                               'revision': None if revisionless else revision, 'qualified_revision': revision}
                    if revisionless:
                        checked['revision_note'] = 'revisão do Hermes não identificada; impressões conferem'
                    manager, _, _ = helper.manager(root, compatible=lambda: checked)
                    self.addCleanup(manager.close)
                    if has_map:
                        helper.call(manager, 'config approve-map base')
                    helper.call(manager, 'mode observe')
                    for command in ('status', 'explain'):
                        payload = helper.call(manager, command)
                        self.assertEqual(payload['compatibility']['host'], checked['host'])
                        self.assertTrue(payload['compatibility']['source_qualified'])
                        self.assertEqual(payload['compatibility']['revision'], checked['revision'])
                        self.assertEqual(payload['compatibility']['qualified_revision'], revision)
                        self.assertNotIn('S2', repr(payload['compatibility']))
                        self.assertFalse(payload['installed_verified'])
                        self.assertEqual(payload['compatibility']['lifecycle'], 'requires_installed_smoke')
                        self.assertEqual(payload['auto_available'], has_map)

    def test_changed_native_source_never_keeps_a_qualified_json_label(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, _, _ = helper.manager(root)
            self.addCleanup(manager.close)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode auto')
            manager.compatible = lambda: {'ok': False, 'reasons': ['native_function_changed']}
            payload = helper.call(manager, 'explain')
            self.assertFalse(payload['compatibility'].get('source_qualified', True))
            self.assertEqual(payload['compatibility']['host'], 'unqualified')
            self.assertFalse(payload['auto_available'])
