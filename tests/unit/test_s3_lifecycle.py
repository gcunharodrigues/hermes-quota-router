"""S3 approved map, Auto commands, closed hooks and generation provenance."""
import copy
from datetime import timedelta
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest

from s2_fakes import NOW, claude, codex, reader_for
from s3_fakes import Backend, TARGET, qualified
from test_s2_commands import Context
from quota_router.lifecycle import Management
from quota_router import mapping


class Registration:
    def __init__(self):
        self.disposed = False

    def dispose(self):
        self.disposed = True


class AutoContext(Context):
    def __init__(self, settings=None):
        super().__init__(settings)
        self.hooks = {}
        self.registrations = []

    def register_hook(self, name, callback, **kwargs):
        self.hooks[name] = callback
        registration = Registration()
        self.registrations.append(registration)
        return registration


class MapTests(unittest.TestCase):
    def test_approved_base_has_provider_specific_efforts_and_cron_follows(self):
        self.assertTrue(hasattr(mapping, 'approved_base'), 'Approved S3 map is missing')
        table = mapping.approved_base()
        self.assertEqual(len(table), 12)
        self.assertEqual(table['cron'], {'follows': 'conversation'})
        self.assertEqual(table['conversation']['anthropic'], {'model': 'claude-opus-5-5', 'effort': 'high'})
        self.assertEqual(table['extract']['openai-codex'], {'model': 'gpt-6-luna', 'effort': 'high'})
        self.assertEqual(table['deep']['anthropic']['effort'], 'xhigh')
        self.assertEqual(table['deep']['openai-codex']['effort'], 'max')
        self.assertEqual(table['general']['anthropic']['model'], 'claude-opus-5-5')
        self.assertEqual(table['triage']['anthropic']['effort'], 'medium')

    def test_catalog_absent_id_excludes_role_and_variants_remain_ineligible(self):
        self.assertTrue(hasattr(mapping, 'catalog_gate'), 'Catalog gate is missing')
        gate = mapping.catalog_gate
        self.assertEqual(gate('anthropic', 'claude-opus-5-5', {'anthropic': []}), 'model_absent_from_catalog')
        self.assertIsNone(gate('anthropic', 'claude-opus-5-5', {'anthropic': ['claude-opus-5-5']}))
        self.assertIsNone(gate('anthropic', 'claude-opus-5-5', {}))
        for model in ('claude-fable-5-2', 'gpt-6-astra'):
            self.assertTrue(gate('anthropic', model, {'anthropic': [model]}).startswith('model_not_eligible:'))

    def test_override_precondition_does_not_echo_key_values(self):
        from quota_router.groups import preconditions
        backend = Backend()
        backend.document['agent']['reasoning_overrides'] = {'GPT-6.1-SOL': 'SYNTHETIC_PRIVATE_VALUE'}
        errors = preconditions(backend.document, 'conversation')
        self.assertEqual(errors, ['agent.reasoning_overrides'])
        self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', repr(errors))


class AutoCommandTests(unittest.TestCase):
    def manager(self, root, context=None, compatible=qualified):
        ctx = context or AutoContext()
        backend = Backend()
        reader = reader_for(openai_codex=codex(100), anthropic=claude(10))
        self.assertIn('backend', __import__('inspect').signature(Management).parameters, 'S3 Auto dependencies are missing')
        m = Management(ctx, importer=lambda: reader, sources=lambda: (backend.read(), []), clock=lambda: NOW,
                       profile=lambda: 'default', backend=backend, data_dir=root, compatible=compatible)
        return m, ctx, backend

    def call(self, m, command):
        return json.loads(m.command(command + ' --json'))

    def test_approval_auto_apply_status_and_off_restore(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = self.manager(root)
            before = backend.read()
            self.assertFalse(self.call(m, 'mode auto')['ok'])
            self.assertEqual(ctx.registrations, [])
            approved = self.call(m, 'config approve-map base')
            self.assertTrue(approved['ok'])
            self.assertEqual(ctx.settings['roles']['cron'], {'follows': 'conversation'})
            auto = self.call(m, 'mode auto')
            self.assertTrue(auto['ok'], auto)
            self.assertEqual(auto['mode_effective'], 'auto')
            self.assertEqual(set(ctx.hooks), {'on_session_open', 'on_kanban_dispatch_tick', 'subagent_start', 'on_session_start', 'api_request_error'})
            status = self.call(m, 'apply')
            self.assertEqual(backend.document['model']['provider'], 'anthropic')
            self.assertEqual(status['applied']['age_s'], 0)
            self.assertGreater(status['applied']['generation'], 0)
            self.assertIn('Auto', m.command('status'))
            self.assertIn('Cron', m.command('explain'))
            self.assertTrue(self.call(m, 'mode off')['ok'])
            self.assertEqual(backend.document, before)
            self.assertTrue(all(r.disposed for r in ctx.registrations))

    def test_invalid_settings_or_compat_suspend_without_writes(self):
        for failure in ('invalid', 'compat'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as root:
                m, ctx, backend = self.manager(root)
                self.call(m, 'config approve-map base')
                self.call(m, 'mode auto')
                count = len(backend.writes)
                if failure == 'invalid':
                    ctx.settings['limits.week_block_pct'] = 999
                else:
                    m.compatible = lambda: {'ok': False, 'reasons': ['native.function']}
                status = self.call(m, 'apply')
                self.assertEqual(len(backend.writes), count)
                self.assertFalse(status['auto_available'])

    def test_unload_preserves_declared_auto_and_reload_reports_absence(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = self.manager(root)
            self.call(m, 'config approve-map base')
            self.call(m, 'mode auto')
            m.close()
            self.assertEqual(ctx.settings['mode'], 'auto')
            self.assertTrue(all(r.disposed for r in ctx.registrations))
            reloaded = Management(ctx, importer=lambda: None, sources=lambda: (backend.read(), []), clock=lambda: NOW + timedelta(hours=1),
                                  profile=lambda: 'default', backend=backend, data_dir=root, compatible=qualified)
            status = self.call(reloaded, 'status')
            self.assertIsNotNone(status['applied']['absence'])
            self.assertEqual(status['applied']['absence']['from'], NOW.timestamp())
            self.assertIsNotNone(status['applied']['last_applied'])

    def test_hook_never_blocks_or_retains_private_payloads(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = self.manager(root)
            self.call(m, 'config approve-map base')
            self.call(m, 'mode auto')
            start = time.monotonic()
            for name, callback in ctx.hooks.items():
                callback(session_id='private-id', child_session_id='private-child', parent_session_id='private-parent',
                         child_goal='PRIVATE_PROMPT', messages=['PRIVATE_MESSAGE'], headers={'authorization': 'PRIVATE_HEADER'},
                         body='PRIVATE_BODY', model='claude-opus-5-5', provider='anthropic', error=RuntimeError('PRIVATE_ERROR'))
            self.assertLess(time.monotonic() - start, 0.5)
            m.wait_hooks()
            text = ''.join(p.read_text() for p in Path(root).glob('*.json'))
            for private in ('private-id', 'private-child', 'private-parent', 'PRIVATE_PROMPT', 'PRIVATE_MESSAGE', 'PRIVATE_HEADER', 'PRIVATE_BODY', 'PRIVATE_ERROR'):
                self.assertNotIn(private, text)
            self.assertIn('geração indeterminada', text)
            m.close()


class CronOriginTests(unittest.TestCase):
    def test_origin_table_and_effort_precedence(self):
        module = importlib.import_module('quota_router.inventory')
        self.assertTrue(hasattr(module, 'cron_origins'), 'S3 cron origin table is missing')
        backend = Backend()
        cfg = backend.document
        cfg['cron']['model'] = 'gpt-6.1-terra'
        cfg['agent']['reasoning_overrides'] = {'gpt-6.1-terra': 'low'}
        jobs = [{'id': 'full', 'provider': 'anthropic', 'model': 'claude-sonnet-5-5', 'reasoning_effort': 'xhigh'},
                {'id': 'partial', 'provider': 'anthropic'}, {'id': 'unpin'}]
        result = module.cron_origins(cfg, jobs)
        self.assertTrue(result['default']['partial'])
        self.assertEqual(result['default']['model']['origin'], 'cron.model')
        self.assertEqual(result['default']['provider']['origin'], 'conversation')
        self.assertEqual(result['default']['effort'], {'value': 'low', 'origin': 'agent.reasoning_overrides'})
        self.assertEqual(result['jobs'][0]['effort'], {'value': 'xhigh', 'origin': 'job'})
        self.assertTrue(result['jobs'][1]['partial'])
        self.assertIn('sem efeito', result['consumers.cron'])


class GenerationTests(unittest.TestCase):
    def correlate(self, history, **changes):
        self.assertIsNotNone(importlib.util.find_spec('quota_router.events'), 'S3 event recorder is missing')
        from quota_router.events import generation_for
        evidence = {'qualified': True, 'started_at': 200, 'model_config': {'provider': 'openai-codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh'},
                    'changed_after_creation': False, 'parent_type': 'common'}
        evidence.update(changes)
        return generation_for(history, evidence, role='conversation')

    def history(self):
        from quota_router.groups import target
        a = target('conversation', {'provider': 'openai-codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh'})
        b = target('conversation', TARGET)
        return [{'generation': 1, 'group': 'conversation', 'at': 100, 'values': a},
                {'generation': 2, 'group': 'conversation', 'at': 300, 'values': b},
                {'generation': 3, 'group': 'conversation', 'at': 400, 'values': a}]

    def test_a_b_a_uses_creation_not_hook_time(self):
        result = self.correlate(self.history())
        self.assertEqual(result['generation'], 1)
        self.assertEqual(result['age_s'], 100)
        self.assertEqual(self.correlate(self.history(), started_at=500)['generation'], 3)

    def test_safety_window_mutation_unknown_source_and_parent_fail_closed(self):
        for changes in ({'started_at': 130}, {'started_at': 410}, {'started_at': 400}, {'qualified': False},
                        {'changed_after_creation': True}, {'parent_type': 'unknown'}, {'model_config': {}}):
            with self.subTest(changes=changes):
                result = self.correlate(self.history(), **changes)
                self.assertEqual(result['state'], 'geração indeterminada')
                self.assertNotIn('age_s', result)

    def test_boundary_sixty_seconds_is_indeterminate_and_follow_has_no_age(self):
        self.assertEqual(self.correlate(self.history(), started_at=160)['state'], 'geração indeterminada')
        result = self.correlate(self.history(), parent_type='follow_profile_config')
        self.assertEqual(result['state'], 'follow_profile_config')
        self.assertNotIn('age_s', result)


if __name__ == '__main__':
    unittest.main()
