"""Review regressions on disposable state, without native account access."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from s2_fakes import NOW
from s3_fakes import qualified
import test_s3_lifecycle as lifecycle_fixtures
from quota_router.lifecycle import Management


class AliasReviewTests(unittest.TestCase):
    def test_shared_nodes_across_group_boundary_refuse_all_write_paths(self):
        from quota_router.apply import Engine
        from s3_fakes import Backend, TARGET
        for role in ('conversation', 'general'):
            for later in (False, True):
                with self.subTest(role=role, later=later), tempfile.TemporaryDirectory() as root:
                    backend = Backend()
                    engine = Engine(root, backend, qualified)
                    if later:
                        engine.cycle({role: TARGET}, 100)
                    node = backend.document['model'] if role == 'conversation' else backend.document['delegation']['backends']['model_map']['options'][0]
                    backend.document['outside'] = node
                    before, count = backend.read(), len(backend.writes)
                    engine.cycle({role: TARGET}, 200)
                    engine.restore(300)
                    self.assertEqual(len(backend.writes), count)
                    self.assertEqual(backend.read(), before)
                    self.assertIn('yaml_alias_crosses_group', engine.report(301)['groups_out'][role])


class CronReviewTests(unittest.TestCase):
    def test_cron_uses_native_parser_and_ordered_alias_resolver(self):
        import sys
        import types
        from unittest import mock
        from quota_router.inventory import cron_origins
        constants = types.ModuleType('hermes_constants')
        def parse(value):
            if value is False:
                return {'enabled': False}
            if isinstance(value, dict):
                return value
            return {'enabled': True, 'effort': value} if value in ('high', 'low', 'medium') else None
        def resolve(model, overrides):
            for name in (model, model.replace('.', '-'), 'openai/' + model.replace('.', '-')):
                parsed = parse(overrides.get(name))
                if parsed is not None:
                    return parsed
            return None
        constants.parse_reasoning_effort = mock.Mock(side_effect=parse)
        constants.resolve_per_model_reasoning_effort = mock.Mock(side_effect=resolve)
        for items in ([('openai/gpt-6-1-terra', 'low'), ('gpt-6-1-terra', 'high')],
                      [('gpt-6-1-terra', 'high'), ('openai/gpt-6-1-terra', 'low')]):
            config = {'model': {'default': 'gpt-6.1-terra'}, 'agent': {'reasoning_effort': 'medium', 'reasoning_overrides': dict(items)}}
            with mock.patch.dict(sys.modules, {'hermes_constants': constants}):
                result = cron_origins(config, [])
            self.assertEqual(result['default']['effort'], {'value': 'high', 'origin': 'agent.reasoning_overrides'})
        self.assertGreater(constants.resolve_per_model_reasoning_effort.call_count, 0)
        self.assertGreater(constants.parse_reasoning_effort.call_count, 0)


class CatalogReviewTests(unittest.TestCase):
    def test_corrupt_catalog_and_etag_are_untouched_and_mutating_loaders_never_called(self):
        from unittest import mock
        import sys
        import types
        from quota_router.mapping import native_catalogs
        with tempfile.TemporaryDirectory() as root:
            cache = Path(root) / 'models_dev_cache.json'
            etag = Path(root) / 'models_dev_cache.etag'
            cache.write_text('{broken')
            etag.write_text('synthetic-etag')
            module = types.ModuleType('agent.models_dev')
            module._models_dev_cache = {}
            module.PROVIDER_TO_MODELS_DEV = {'openai-codex': 'openai', 'anthropic': 'anthropic'}
            module._get_cache_path = lambda: cache
            def mutating(**_kwargs):
                cache.rename(cache.with_suffix('.corrupt'))
                etag.unlink()
                return {}
            module.fetch_models_dev = mock.Mock(side_effect=mutating)
            module._load_disk_cache = mock.Mock(side_effect=AssertionError('Forbidden loader'))
            before = {p.name: p.read_bytes() for p in Path(root).iterdir()}
            with mock.patch.dict(sys.modules, {'agent.models_dev': module}):
                self.assertEqual(native_catalogs(), {})
            self.assertEqual({p.name: p.read_bytes() for p in Path(root).iterdir()}, before)
            module.fetch_models_dev.assert_not_called()
            module._load_disk_cache.assert_not_called()


class WorkerContextReviewTests(unittest.TestCase):
    def test_worker_uses_owner_context_not_process_default_home(self):
        from contextvars import ContextVar
        from quota_router.events import HookWorker
        from threading import Event
        home = ContextVar('synthetic_profile_home', default='other-process-profile')
        token = home.set('default-owner-profile')
        seen = []
        done = Event()
        def cycle():
            seen.append(home.get())
            done.set()
        worker = HookWorker(None, cycle, lambda: NOW)
        self.addCleanup(worker.close)
        home.reset(token)
        worker.callback('on_session_open')()
        self.assertTrue(done.wait(2))
        worker.wait()
        self.assertEqual(seen, ['default-owner-profile'])


class HysteresisReviewTests(unittest.TestCase):
    def test_auto_drops_preferences_for_removed_roles(self):
        helper = lifecycle_fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend = helper.manager(root)
            self.addCleanup(manager.close)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode auto')
            backend.document['delegation']['backends']['model_map']['options'] = []
            helper.call(manager, 'apply')
            self.assertEqual({key[0] for key in manager.preferences}, {'conversation'})
            self.assertEqual(set(manager.preference_routes), {'conversation'})

    def test_auto_keeps_preference_across_own_writes_and_repeated_small_inversions(self):
        from s2_fakes import codex, claude, reader_for
        helper = lifecycle_fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend = helper.manager(root)
            self.addCleanup(manager.close)
            snapshots = {'openai_codex': codex(30, week_reset_h=84), 'anthropic': claude(10, week_reset_h=84)}
            manager.importer = lambda: reader_for(**snapshots)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode auto')
            self.assertEqual(backend.read()['delegation']['backends']['model_map']['options'][0]['provider'], 'anthropic')
            snapshots.update(openai_codex=codex(5, week_reset_h=84), anthropic=claude(10, week_reset_h=84))
            count = len(backend.writes)
            for _ in range(5):
                manager.cache.clear()
                helper.call(manager, 'apply')
                self.assertEqual(backend.read()['delegation']['backends']['model_map']['options'][0]['provider'], 'anthropic')
            self.assertEqual(len(backend.writes), count)
            self.assertEqual(len(manager.preferences), len({key[0] for key in manager.preferences}))
            snapshots.update(openai_codex=codex(0, week_reset_h=84), anthropic=claude(20, week_reset_h=84))
            manager.cache.clear()
            helper.call(manager, 'apply')
            self.assertEqual(backend.read()['delegation']['backends']['model_map']['options'][0]['provider'], 'openai-codex')


class JournalReviewTests(unittest.TestCase):
    def test_divergent_reread_stops_two_group_cycle_and_preserves_intention(self):
        from quota_router.apply import Engine
        from s3_fakes import Backend, TARGET
        for restoring in (False, True):
            with self.subTest(restoring=restoring), tempfile.TemporaryDirectory() as root:
                backend = Backend()
                engine = Engine(root, backend, qualified)
                if restoring:
                    engine.cycle({'conversation': TARGET, 'general': TARGET}, now=100)
                original_write = backend.write
                def divergent(updates, unset):
                    original_write(updates, unset)
                    backend.document['model']['provider'] = 'anthropic' if restoring else 'openai-codex'
                backend.write = divergent
                count = len(backend.writes)
                if restoring:
                    engine.restore(200)
                else:
                    engine.cycle({'conversation': TARGET, 'general': TARGET}, now=200)
                journal = json.loads((Path(root) / 'journal.json').read_text())
                self.assertEqual(journal['group'], 'conversation')
                self.assertEqual(len(backend.writes), count + 1)
                engine.backend.write = original_write
                self.assertTrue(engine.recover())
                self.assertFalse((Path(root) / 'journal.json').exists())


class FailureLatchReviewTests(unittest.TestCase):
    def test_failure_latch_prevents_writes_after_reader_recovers_until_reload(self):
        from s2_fakes import codex, claude, reader_for
        helper = lifecycle_fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend = helper.manager(root)
            self.addCleanup(manager.close)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode auto')
            original = backend.read
            def unreadable():
                raise OSError('SYNTHETIC_PRIVATE_FAILURE')
            backend.read = unreadable
            self.assertFalse(helper.call(manager, 'apply')['ok'])
            backend.read = original
            manager.importer = lambda: reader_for(openai_codex=codex(10), anthropic=claude(100))
            manager.cache.clear()
            count, before = len(backend.writes), backend.read()
            for command in ('apply', 'status', 'explain', 'apply'):
                result = helper.call(manager, command)
                self.assertFalse(result['auto_available'])
                self.assertEqual(result['auto_reason'], 'native_state_or_config_unavailable')
            self.assertEqual(backend.read(), before)
            self.assertEqual(len(backend.writes), count)


class RestoreReviewTests(unittest.TestCase):
    def test_off_refuses_unreadable_retained_directory_even_when_stat_hides_state(self):
        helper = lifecycle_fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            data = Path(root) / 'data'
            manager, ctx, backend = helper.manager(data)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode auto')
            manager.close()
            before = backend.read()
            ctx.settings['limits.week_block_pct'] = 999
            data.chmod(0o000)
            loaded = None
            try:
                loaded = Management(ctx, backend=backend, data_dir=data, compatible=qualified,
                                    sources=lambda: (backend.read(), []), profile=lambda: 'default', clock=lambda: NOW)
                result = helper.call(loaded, 'mode off')
                self.assertFalse(result['ok'], result)
                self.assertEqual(ctx.settings['mode'], 'auto')
                self.assertEqual(backend.read(), before)
            finally:
                data.chmod(0o700)
                if loaded is not None:
                    loaded.close()

    def test_off_after_suspended_reload_requires_proven_restoration(self):
        helper = lifecycle_fixtures.AutoCommandTests()
        for failure in ('compatibility', 'invalid_settings'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as root:
                manager, ctx, backend = helper.manager(root)
                baseline = backend.read()
                helper.call(manager, 'config approve-map base')
                helper.call(manager, 'mode auto')
                manager.close()
                good = [False]
                if failure == 'invalid_settings':
                    ctx.settings['limits.week_block_pct'] = 999
                compatible = lambda: qualified() if good[0] or failure != 'compatibility' else {'ok': False, 'reasons': ['changed']}
                loaded = Management(ctx, backend=backend, data_dir=root, compatible=compatible,
                                    sources=lambda: (backend.read(), []), profile=lambda: 'default', clock=lambda: NOW)
                self.addCleanup(loaded.close)
                before, count = backend.read(), len(backend.writes)
                result = helper.call(loaded, 'mode off')
                self.assertFalse(result['ok'], result)
                self.assertEqual(ctx.settings['mode'], 'auto')
                self.assertEqual(backend.read(), before)
                self.assertEqual(len(backend.writes), count)
                self.assertTrue(json.loads((Path(root) / 'state.json').read_text())['auto_declared'])
                good[0] = True
                ctx.settings.pop('limits.week_block_pct', None)
                result = helper.call(loaded, 'mode off')
                self.assertTrue(result['ok'], result)
                self.assertEqual(backend.read(), baseline)
                self.assertFalse(json.loads((Path(root) / 'state.json').read_text())['auto_declared'])
