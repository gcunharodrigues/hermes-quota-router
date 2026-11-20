"""Revisão da simplificação, 2026-11-18 (decisions/log.md): each test failed before its fix."""
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest import mock

from s2_fakes import CREDITS_OK, NOW, claude, codex
from s3_fakes import Backend, qualified
from test_s3_lifecycle import AutoContext
from quota_router import groups, mapping, storage
from quota_router.apply import Engine, locked_pair
from quota_router.lifecycle import Management


def call(manager, command):
    return json.loads(manager.command(command + ' --json'))


class RestartSeedTests(unittest.TestCase):
    """F1/F2: the applied route seeds the hysteresis only once per role, right after a restart."""

    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.ctx, self.backend, self.used = AutoContext(), Backend(), {'codex': 70}

    def reader(self, provider):
        return codex(self.used['codex']) if provider == 'openai-codex' else claude(40)

    def build(self):
        manager = Management(self.ctx, importer=lambda: self.reader, sources=lambda: (self.backend.read(), []),
                             clock=lambda: NOW, profile=lambda: 'default', backend=self.backend, data_dir=self.root.name,
                             compatible=qualified)
        self.addCleanup(manager.close)
        return manager

    def general(self):
        options = self.backend.document['delegation']['backends']['model_map']['options']
        return next(option['provider'] for option in options if option['name'] == 'general')

    def held_at_62(self):
        m = self.build()
        call(m, 'config approve-map base')
        self.assertEqual(call(m, 'mode auto')['mode_effective'], 'auto')
        call(m, 'apply')
        self.assertEqual(self.general(), 'anthropic')
        self.used['codex'] = 62
        m.cache.clear()
        call(m, 'apply')
        self.assertEqual(self.general(), 'anthropic')
        return m

    # Reviewer scenario (hqr-f5-review/test_zz_settings_hysteresis.py): a settings change starts a new history.
    def test_settings_change_restarts_preference_history_without_a_restart(self):
        m = self.held_at_62()
        call(m, 'config set limits.session_block_pct 96')
        m.cache.clear()
        call(m, 'apply')
        self.assertEqual(self.general(), 'openai-codex')

    def test_settings_change_after_a_restart_does_not_reseed_the_applied_route(self):
        self.held_at_62().close()
        restarted = self.build()
        call(restarted, 'apply')
        self.assertEqual(self.general(), 'anthropic')
        call(restarted, 'config set limits.session_block_pct 96')
        restarted.cache.clear()
        call(restarted, 'apply')
        self.assertEqual(self.general(), 'openai-codex')

    def applied_on_credits(self):
        """Both subscriptions exhausted: the principal's paid credits choose openai-codex for general."""
        phase = {'credits': True}
        self.reader = lambda provider: ((codex(100, credits=CREDITS_OK) if provider == 'openai-codex' else claude(100))
                                        if phase['credits'] else
                                        codex(66) if provider == 'openai-codex' else claude(40))
        m = self.build()
        call(m, 'config approve-map base')
        self.assertEqual(call(m, 'mode auto')['mode_effective'], 'auto')
        self.assertEqual(call(m, 'apply')['decisions']['routes']['general']['tier'], 'credits')
        self.assertEqual(self.general(), 'openai-codex')
        m.close()
        # After the restart both subscriptions are free again; without a preference anthropic ranks first at 66%.
        phase['credits'] = False

    def test_restart_does_not_seed_a_route_applied_on_credits(self):
        self.applied_on_credits()
        call(self.build(), 'apply')
        self.assertEqual(self.general(), 'anthropic')

    def test_restart_does_not_seed_from_legacy_state_without_a_tier(self):
        self.held_at_62().close()
        path = Path(self.root.name) / 'state.json'
        state = json.loads(path.read_text())
        for entry in state['groups'].values():
            entry.pop('tier', None)
        path.write_text(json.dumps(state))
        # At 62% openai-codex ranks first without a preference (see the settings-change tests above).
        call(self.build(), 'apply')
        self.assertEqual(self.general(), 'openai-codex')


class AliasMemoTests(unittest.TestCase):
    """F3: the reference counts kept for one document object fail closed when that object changes in place."""

    def test_an_alias_created_in_place_after_the_count_is_detected(self):
        document = {'a': {'x': 1}, 'b': {'y': 2}}
        self.assertFalse(groups.aliased(document, [('a', 'x')]))
        document['b'] = document['a']
        self.assertTrue(groups.aliased(document, [('a', 'x')]))

    def test_an_alias_that_keeps_equal_content_is_detected(self):
        document = {'a': {'x': 1}, 'b': {'x': 1}}
        self.assertFalse(groups.aliased(document, [('a', 'x')]))
        document['b'] = document['a']
        self.assertTrue(groups.aliased(document, [('a', 'x')]))

    def test_a_node_added_in_place_on_the_path_is_counted_instead_of_raising(self):
        document = {'a': {'x': 1}}
        self.assertFalse(groups.aliased(document, [('a', 'x')]))
        document['a'] = {'x': {'n': 1}}
        self.assertFalse(groups.aliased(document, [('a', 'x', 'n')]))
        document['b'] = document['a']['x']
        self.assertTrue(groups.aliased(document, [('a', 'x', 'n')]))

    def test_preconditions_count_an_equal_copy_put_in_place_instead_of_raising(self):
        document = {'model': {'provider': 'anthropic', 'default': 'claude-opus-5-5'}}
        self.assertEqual(groups.preconditions(document, 'conversation'), [])
        document['model'] = {'provider': 'anthropic', 'default': 'claude-opus-5-5'}
        self.assertEqual(groups.preconditions(document, 'conversation'), [])
        document['other'] = document['model']
        self.assertEqual(groups.preconditions(document, 'conversation'), ['yaml_alias_crosses_group'])

    def test_a_node_the_counts_cannot_know_counts_as_aliased(self):
        document = {'a': {'x': 1}}
        self.assertFalse(groups.aliased(document, [('a', 'x')]))
        original = groups._count
        self.addCleanup(setattr, groups, '_count', original)
        groups._count = lambda _document: {}
        self.assertTrue(groups.aliased({'a': {'x': 1}}, [('a', 'x')]))

    def test_an_unchanged_document_keeps_its_verdicts(self):
        shared = {'x': 1}
        document = {'a': shared, 'b': shared, 'c': {'y': 2}}
        for _ in range(2):
            self.assertTrue(groups.aliased(document, [('a', 'x')]))
            self.assertFalse(groups.aliased(document, [('c', 'y')]))


def holds_key(value, key, depth=4):
    if isinstance(value, dict):
        return key in value or depth > 0 and any(holds_key(child, key, depth - 1) for child in value.values())
    if isinstance(value, (list, tuple)):
        return depth > 0 and any(holds_key(child, key, depth - 1) for child in value)
    return False


class CatalogFileMemoTests(unittest.TestCase):
    """F5: only the extracted catalogs are kept per file stamp, never the whole models.dev document."""

    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.path = Path(root.name) / 'models_dev_cache.json'
        self.path.write_text(json.dumps({'anthropic': {'models': {'claude-opus-5-5': {}}},
                                         'unrelated-provider': {'models': {'big-model': {}}}}), encoding='utf-8')
        self.module = types.ModuleType('agent.models_dev')
        self.module._models_dev_cache, self.module._get_cache_path = {}, lambda: self.path
        self.module.PROVIDER_TO_MODELS_DEV = {'anthropic': 'anthropic', 'openai-codex': 'openai'}
        patcher = mock.patch.dict('sys.modules', {'agent.models_dev': self.module})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_parsed_document_is_not_kept(self):
        self.assertEqual(mapping.native_catalogs(), {'anthropic': ['claude-opus-5-5']})
        self.assertFalse(any(holds_key(value, 'unrelated-provider') for value in vars(mapping).values()))

    def test_a_changed_provider_map_is_not_answered_from_the_kept_catalogs(self):
        self.assertEqual(mapping.native_catalogs(), {'anthropic': ['claude-opus-5-5']})
        self.module.PROVIDER_TO_MODELS_DEV = {'anthropic': 'unrelated-provider', 'openai-codex': 'openai'}
        self.assertEqual(mapping.native_catalogs(), {'anthropic': ['big-model']})

    def test_a_caller_changing_its_answer_does_not_change_the_kept_catalogs(self):
        mapping.native_catalogs()['anthropic'].append('injected')
        self.assertEqual(mapping.native_catalogs(), {'anthropic': ['claude-opus-5-5']})


class EngineThreadOwnershipTests(unittest.TestCase):
    """F6: the lock's directory descriptor belongs to the thread holding auto.lock, not to every thread."""

    def setUp(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.main = Engine(root.name, Backend(), compatible=lambda: {'ok': True})
        self.aux = Engine(root.name, self.main.backend, compatible=lambda: {'ok': True},
                          state_name='aux-state.json', journal_name='aux-journal.json', kind='auxiliary')
        with self.main.locked():
            self.main.persist('probe.json', {'value': 1})

    def from_other_thread(self, action):
        """Run `action` in a second thread while this thread holds the main and auxiliary lock."""
        outcome = {}

        def run():
            try:
                outcome['value'] = action()
            except Exception as error:
                outcome['error'] = error

        with locked_pair(self.main, self.aux):
            self.main.require_locked()
            self.aux.require_locked()
            thread = threading.Thread(target=run)
            thread.start()
            thread.join(5)
        return outcome

    def test_another_thread_is_not_locked(self):
        for engine in (self.main, self.aux):
            with self.subTest(kind=engine.kind):
                self.assertIsInstance(self.from_other_thread(engine.require_locked).get('error'), RuntimeError)

    def test_another_thread_cannot_persist_through_the_holders_descriptor(self):
        outcome = self.from_other_thread(lambda: self.main.persist('probe.json', {'value': 2}))
        self.assertIsInstance(outcome.get('error'), RuntimeError)
        self.assertEqual(self.main.read_record('probe.json'), {'value': 1})

    def test_another_thread_reads_through_its_own_descriptor(self):
        opened = []
        original = storage.directory

        def directory(*args, **kwargs):
            opened.append(threading.get_ident())
            return original(*args, **kwargs)

        with mock.patch.object(storage, 'directory', directory):
            outcome = self.from_other_thread(lambda: (threading.get_ident(), self.main.read_record('probe.json')))
        reader, value = outcome['value']
        self.assertEqual(value, {'value': 1})
        self.assertIn(reader, opened)


if __name__ == '__main__':
    unittest.main()
