# Contract: decisions/aux-plan.md, AUXP-02/03/04, H1-H11/H13/H19-H22.
"""Real management entry points with disposable engines and synthetic native contracts."""
from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from quota_router.lifecycle import Management
from quota_router.mapping import approved_auxiliary, approved_base
from s2_fakes import NOW, claude, codex, reader_for
from s3_fakes import Backend, qualified
from test_s3_lifecycle import AutoContext


class AuxiliaryLifecycleTests(unittest.TestCase):
    def manager(self, root, *, enabled=True, conversation=True, **kwargs):
        backend = kwargs.pop('backend', Backend())
        if 'auxiliary' not in backend.document:
            backend.document['auxiliary'] = {
                task: dict(provider='openai-codex', model=row['openai-codex']['model'],
                           reasoning_effort=row['openai-codex']['effort'])
                for task, row in approved_auxiliary().items()}
            del backend.document['auxiliary']['voice_chat']['reasoning_effort']
            backend.document['auxiliary']['background_review']['enabled'] = True
            backend.document['image_gen'] = {'model': 'synthetic-fixed'}
        ctx = kwargs.pop('ctx', AutoContext({'roles': approved_base(), 'auxiliary_map': approved_auxiliary(),
                                           'consumers.auxiliary': enabled, 'consumers.conversation': conversation,
                                           'conversation.policy': 'pacing'}))
        snapshots = {'openai_codex': codex(100), 'anthropic': claude(10)}
        def importer():
            return reader_for(**snapshots)
        manager = Management(ctx, importer=importer, sources=lambda: (backend.read(), []),
                             clock=kwargs.pop('clock', lambda: NOW), profile=lambda: 'default',
                             backend=backend, data_dir=root, compatible=qualified, catalogs=lambda: {},
                             auxiliary_compatible=kwargs.pop('auxiliary_compatible', qualified),
                             auxiliary_registry=kwargs.pop('auxiliary_registry', lambda: {'ok': True, 'tasks': {}}), **kwargs)
        self.addCleanup(manager.close)
        return manager, ctx, backend, snapshots

    def call(self, manager, command):
        return json.loads(manager.command(command + ' --json'))

    def test_auto_routes_all_tasks_then_off_restores_exact_baseline_without_map_or_registry(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, b, _ = self.manager(root)
            baseline = b.read()
            result = self.call(m, 'mode auto')
            self.assertTrue(result['ok'], result)
            for task, pair in approved_auxiliary().items():
                node = b.read()['auxiliary'][task]
                self.assertEqual(node['provider'], 'anthropic')
                self.assertEqual(node['model'], pair['anthropic']['model'])
                self.assertEqual(node.get('reasoning_effort'), pair['anthropic'].get('effort'))
            self.assertEqual(result['decisions']['auxiliary']['source']['path'], 'conversation')
            self.assertEqual(len(result['applied']['auxiliary']['groups']), 11)
            self.assertFalse(any(k.startswith('aux:') for k in result['applied']['groups']))
            self.assertTrue(Path(root, 'aux-state.json').is_file())
            ctx.settings['auxiliary_map'] = {}
            m.catalogs = lambda: {'anthropic': []}
            m.auxiliary_registry = lambda: {'ok': False}
            result = self.call(m, 'mode off')
            self.assertTrue(result['ok'], result)
            self.assertEqual(b.read(), baseline)
            self.assertFalse(Path(root, 'aux-journal.json').exists())
            self.assertFalse(result['applied']['auxiliary']['restoration_pending'])

    def test_default_off_previews_without_creating_engine_or_writing_auxiliary(self):
        with tempfile.TemporaryDirectory() as root:
            m, _, b, _ = self.manager(root, enabled=False)
            baseline = b.read()['auxiliary']
            result = self.call(m, 'mode observe')
            task = result['decisions']['auxiliary']['tasks']['compression']
            self.assertEqual(task['state'], 'preview_only')
            self.assertEqual(task['choice'], 'anthropic')
            self.assertTrue(task['would_change'])
            self.assertIsNone(m.aux_engine)
            self.assertEqual(b.writes, [])
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            self.assertEqual(b.read()['auxiliary'], baseline)
            self.assertFalse(Path(root, 'aux-state.json').exists())
            self.assertIn('Auxiliares desligadas', m.command('status'))

    def test_computed_source_is_separate_and_preserves_hysteresis_across_blocked_conversation(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, b, snapshots = self.manager(root)
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            ctx.settings['consumers.conversation'] = False
            # Settings revision changes reset the auxiliary preference; first choose Claude on a strong advantage.
            snapshots.update(openai_codex=codex(75, week_reset_h=120), anthropic=claude(10))
            m.cache.clear()
            result = self.call(m, 'status')
            self.assertEqual(result['decisions']['auxiliary']['source']['path'], 'computed')
            self.assertEqual(result['decisions']['auxiliary']['source']['choice'], 'anthropic')
            count = len(b.writes)
            snapshots.update(openai_codex=codex(9, week_reset_h=120), anthropic=claude(10))
            m.cache.clear()
            result = self.call(m, 'status')
            self.assertEqual(result['decisions']['auxiliary']['source']['choice'], 'anthropic')
            self.assertEqual(len(b.writes), count)
            self.assertEqual(len(m.auxiliary_preference), 1)
            self.assertFalse(any(key[0].startswith('aux') for key in m.preferences))
            self.assertNotIn('auxiliary', result['routing_blocks'])

    def test_manual_edit_excludes_while_disabled_consumer_restores_other_tasks(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, b, _ = self.manager(root)
            baseline = b.read()
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            b.document['auxiliary']['compression']['provider'] = 'auto'
            edited = deepcopy(b.document['auxiliary']['compression'])
            ctx.settings['consumers.auxiliary'] = False
            result = self.call(m, 'status')
            self.assertEqual(b.read()['auxiliary']['compression'], edited)
            for task in approved_auxiliary():
                if task != 'compression':
                    self.assertEqual(b.read()['auxiliary'][task], baseline['auxiliary'][task])
            self.assertEqual(result['applied']['auxiliary']['groups_out']['aux:compression'], ['auxiliary.compression.provider'])
            self.assertTrue(self.call(m, 'mode off')['ok'])
            self.assertEqual(b.read()['auxiliary']['compression'], edited)

    def test_auxiliary_drift_allows_main_off_but_retains_visible_pending_until_retry(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, b, _ = self.manager(root)
            baseline = b.read()
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            applied = b.read()['auxiliary']
            m.auxiliary_compatible = lambda: {'ok': False, 'reasons': ['agent.auxiliary_client.call_llm'], 'fingerprint_failure': True}
            result = self.call(m, 'mode off')
            self.assertTrue(result['ok'], result)
            self.assertEqual(ctx.settings['mode'], 'off')
            self.assertEqual(b.read()['model'], baseline['model'])
            self.assertEqual(b.read()['auxiliary'], applied)
            self.assertTrue(result['applied']['auxiliary']['restoration_pending'])
            self.assertIn('restauração pendente', m.command('status'))
            m.close()
            m, _, b, _ = self.manager(root, ctx=ctx, backend=b)
            result = self.call(m, 'mode off')
            self.assertTrue(result['ok'], result)
            self.assertFalse(result['applied']['auxiliary']['restoration_pending'])
            self.assertEqual(b.read(), baseline)

    def test_registry_or_fingerprint_failure_suspends_auxiliary_only_and_off_ignores_registry(self):
        for dependency in ('registry', 'fingerprint'):
            with self.subTest(dependency=dependency), tempfile.TemporaryDirectory() as root:
                extra = ({'auxiliary_registry': lambda: {'ok': False}} if dependency == 'registry' else
                         {'auxiliary_compatible': lambda: {'ok': False, 'reasons': ['auxiliary_host_requalification_required'], 'fingerprint_failure': True}})
                m, _, b, _ = self.manager(root, **extra)
                before = b.read()['auxiliary']
                result = self.call(m, 'mode auto')
                self.assertTrue(result['ok'], result)
                self.assertEqual(b.read()['model']['provider'], 'anthropic')
                self.assertEqual(b.read()['auxiliary'], before)
                self.assertIsNone(result['decisions']['auxiliary']['tasks']['compression']['choice'])
                self.assertTrue(self.call(m, 'mode off')['ok'])

    def test_reload_marks_auxiliary_absence_and_blocked_source_does_not_fallback_on_no_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, b, snapshots = self.manager(root)
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            m.close()
            m, _, _, _ = self.manager(root, ctx=ctx, backend=b, clock=lambda: NOW + timedelta(minutes=1))
            self.assertIsNotNone(m.aux_engine.absence)
            self.assertEqual(m.aux_engine.absence['from'], NOW.timestamp())
            self.assertTrue(self.call(m, 'mode off')['ok'])

    def test_auto_recalculates_both_decisions_under_one_shared_lock(self):
        from unittest.mock import patch
        from quota_router import storage
        with tempfile.TemporaryDirectory() as root:
            m, _, b, _ = self.manager(root)
            calls = []
            original = m.decisions
            def checked(*args, **kwargs):
                if m.engine and m.engine._directory_fd is not None:
                    self.assertEqual(m.engine._directory_fd, m.aux_engine._directory_fd)
                    calls.append('locked')
                return original(*args, **kwargs)
            m.decisions = checked
            self.assertTrue(self.call(m, 'mode auto')['ok'])
            self.assertTrue(calls)
            opened = []
            real_open = storage.open_record
            def record(fd, name, *args, **kwargs):
                if name == 'auto.lock':
                    opened.append(name)
                return real_open(fd, name, *args, **kwargs)
            with patch.object(storage, 'open_record', side_effect=record):
                result = self.call(m, 'status')
            self.assertTrue(result['ok'], result)
            self.assertEqual(len(opened), 1)
