# decisions/aux-plan.md, AUXP-03/04 and H9/H10/H15/H18/H19: real Engine over synthetic data.
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from quota_router import auxiliary
from quota_router.apply import Engine, durable, locked_pair
from s3_fakes import Backend, TARGET, qualified

AUX = {'provider': 'anthropic', 'model': 'claude-sonnet-5-5', 'effort': 'low'}


def backend():
    result = Backend()
    result.document['auxiliary'] = {'approval': {'provider': 'openai-codex', 'model': 'gpt-6.1-terra',
                                                'timeout': 40, 'fallback_chain': ['synthetic']}}
    return result


def engines(root, data, **kwargs):
    main = Engine(root, data, qualified)
    aux = Engine(root, data, qualified, kind='auxiliary', state_name='aux-state.json', journal_name='aux-journal.json', **kwargs)
    return main, aux


class AuxiliaryStateTests(unittest.TestCase):
    def test_pair_shared_descriptor_single_lock_and_exact_absent_restore(self):
        with tempfile.TemporaryDirectory() as root:
            data = backend()
            before = copy.deepcopy(data.document)
            main, aux = engines(root, data)
            from quota_router import storage
            native_open = storage.open_record
            opened = []
            def traced(fd, name, *args):
                opened.append(name)
                return native_open(fd, name, *args)
            with mock.patch.object(storage, 'open_record', side_effect=traced), locked_pair(main, aux):
                self.assertEqual(main._directory_fd, aux._directory_fd)
                self.assertTrue(main.begin_locked())
                self.assertTrue(aux.begin_locked())
                main.cycle_locked({'conversation': TARGET}, 100)
                aux.cycle_locked({'aux:approval': AUX}, 100)
                self.assertTrue(aux.needs_restoration_locked())
                self.assertEqual(aux.loaded_locked(120)['absence']['from'], 100)
                self.assertTrue(aux.restore_locked(200))
                self.assertTrue(main.restore_locked(200))
                self.assertFalse(aux.needs_restoration_locked())
            self.assertEqual(opened.count('auto.lock'), 1)
            self.assertEqual(data.document, before)
            self.assertIsNone(aux._directory_fd)
            state = json.loads((Path(root) / 'state.json').read_text())
            Engine.validate_state(state)
            self.assertEqual(set(state['groups']), {'conversation'})
            retained = json.loads((Path(root) / 'aux-state.json').read_text())
            self.assertEqual(set(retained['groups']), {'aux:approval'})
            self.assertFalse((Path(root) / 'aux-journal.json').exists())
            with self.assertRaises(ValueError):
                Engine.validate_state(retained)

    def test_aux_cannot_lock_itself_or_use_locked_bodies_without_pair(self):
        with tempfile.TemporaryDirectory() as root:
            main, aux = engines(root, backend())
            for operation in (lambda: aux.cycle({}, 100), lambda: aux.restore(100), aux.begin, aux.recover,
                              aux.needs_restoration, lambda: aux.loaded(100), lambda: aux.cycle_locked({}, 100),
                              lambda: aux.restore_locked(100), aux.begin_locked, aux.needs_restoration_locked,
                              lambda: aux.loaded_locked(100), aux.recover_locked):
                with self.subTest(operation=operation), self.assertRaises(RuntimeError):
                    operation()
            with locked_pair(main, aux):
                with self.assertRaises(RuntimeError):
                    with main.locked():
                        self.fail('nested lock must fail before opening a second descriptor')

    def test_separate_state_names_validation_and_pair_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            data = backend()
            main = Engine(root, data, qualified)
            aux = Engine(root, data, qualified, kind='auxiliary', state_name='tasks.json', journal_name='intent.json')
            with locked_pair(main, aux):
                aux.cycle_locked({'aux:approval': AUX}, 100)
            self.assertTrue((Path(root) / 'tasks.json').exists())
            for options in ({'kind': 'bad'}, {'state_name': '../escape'}, {'journal_name': 'auto.lock'},
                            {'state_name': 'same.json', 'journal_name': 'same.json'}, {'kind': 'auxiliary'}):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    Engine(root, data, qualified, **options)
            wrong = Engine(Path(root) / 'other', data, qualified, kind='auxiliary', state_name='a.json', journal_name='b.json')
            with self.assertRaises(ValueError):
                with locked_pair(main, wrong):
                    self.fail('different lock directories')
            durable(Path(root) / 'tasks.json', {'schema': 1, 'groups': {'conversation': {}}, 'generation': 0})
            with self.assertRaises(ValueError):
                with locked_pair(main, aux):
                    self.fail('cross-kind empty entry must be rejected')
            self.assertIsNone(main._directory_fd)
            self.assertIsNone(aux._directory_fd)
            with main.locked():
                pass

    def test_manual_edits_and_sensitive_additions_exclude_without_secret_persistence(self):
        for field in ('provider', 'model', 'reasoning_effort', 'base_url', 'api_mode', 'api_key', 'key_env', 'api_key_env', 'extra_body'):
            for later in (False, True):
                with self.subTest(field=field, later=later), tempfile.TemporaryDirectory() as root:
                    data = backend()
                    main, aux = engines(root, data)
                    with locked_pair(main, aux):
                        if later:
                            aux.cycle_locked({'aux:approval': AUX}, 100)
                        value = {'provider': 'auto', 'model': 'gpt-manual-model', 'reasoning_effort': 'high',
                                 'base_url': 'custom', 'api_mode': 'custom'}.get(field, 'SYNTHETIC_PRIVATE_AUX_VALUE')
                        if field == 'extra_body':
                            value = {'reasoning': value}
                        data.document['auxiliary']['approval'][field] = value
                        before, count = copy.deepcopy(data.document), len(data.writes)
                        # Pre-enrollment valid manual pins are excluded by the lifecycle's map gate, not the Engine.
                        if not later and field in ('model', 'reasoning_effort'):
                            self.assertEqual(auxiliary.preconditions(data.document, 'aux:approval'), [])
                            continue
                        aux.cycle_locked({'aux:approval': AUX}, 200)
                        self.assertTrue(aux.restore_locked(300))
                        self.assertEqual(data.document, before)
                        self.assertEqual(len(data.writes), count)
                        self.assertIn('auxiliary.approval.' + field, aux.report(301)['groups_out']['aux:approval'])
                        text = repr(aux.report(301)) + ''.join(p.read_text() for p in Path(root).glob('*.json'))
                        self.assertNotIn('SYNTHETIC_PRIVATE_AUX_VALUE', text)

    def test_disable_restores_without_map_catalog_or_registry_and_approval_removes_effort(self):
        with tempfile.TemporaryDirectory() as root:
            data = backend()
            data.document['auxiliary']['approval']['reasoning_effort'] = 'low'
            before = copy.deepcopy(data.document)
            main, aux = engines(root, data)
            with locked_pair(main, aux):
                aux.cycle_locked({'aux:approval': {k: v for k, v in AUX.items() if k != 'effort'}}, 100)
                self.assertNotIn('reasoning_effort', data.document['auxiliary']['approval'])
                data.document['auxiliary']['approval']['timeout'] = 80
                aux.cycle_locked({}, 200, enabled=set())
                before['auxiliary']['approval']['timeout'] = 80
                self.assertEqual(data.document, before)
                self.assertFalse(aux.state['groups']['aux:approval']['active'])

    def test_four_recovery_cases_retain_original_baseline_and_idempotence(self):
        for restoring in (False, True):
            for case in ('prior', 'target', 'mixture', 'third'):
                with self.subTest(restoring=restoring, case=case), tempfile.TemporaryDirectory() as root:
                    data = backend()
                    main, aux = engines(root, data)
                    with locked_pair(main, aux):
                        aux.cycle_locked({'aux:approval': AUX}, 100)
                        entry = aux.state['groups']['aux:approval']
                        baseline = copy.deepcopy(entry['baseline'])
                        prior = entry['last'] if restoring else baseline
                        target = baseline if restoring else entry['last']
                        aux.persist(aux.journal_name, {'group': 'aux:approval', 'prior': prior, 'target': target,
                                                      'at': 200, 'restore': restoring})
                        projection = copy.deepcopy(prior if case in ('prior', 'mixture', 'third') else target)
                        if case == 'mixture':
                            projection['provider'] = target['provider']
                        if case == 'third':
                            projection['model'] = {'present': True, 'value': 'gpt-manual-model'}
                        data.write(*auxiliary.changes(data.document, 'aux:approval', projection))
                    fresh_main, fresh_aux = engines(root, data)
                    before, count = copy.deepcopy(data.document), len(data.writes)
                    with locked_pair(fresh_main, fresh_aux):
                        self.assertTrue(fresh_aux.recover_locked())
                        if case in ('prior', 'third'):
                            self.assertEqual(data.document, before)
                            self.assertEqual(len(data.writes), count)
                        else:
                            self.assertEqual(auxiliary.project(data.document, 'aux:approval'), target)
                        self.assertEqual(fresh_aux.state['groups']['aux:approval']['baseline'], baseline)
                        state = copy.deepcopy(fresh_aux.state)
                        self.assertTrue(fresh_aux.recover_locked())
                        self.assertEqual(fresh_aux.state, state)
                        self.assertFalse(fresh_aux.read_record(fresh_aux.journal_name))

    def test_aux_compat_drift_retains_pending_but_does_not_block_main_restore(self):
        with tempfile.TemporaryDirectory() as root:
            data = backend()
            before = copy.deepcopy(data.document)
            main, aux = engines(root, data)
            with locked_pair(main, aux):
                main.cycle_locked({'conversation': TARGET}, 100)
                aux.cycle_locked({'aux:approval': AUX}, 100)
                aux.compatible = lambda: {'ok': False, 'reasons': ['auxiliary_symbol']}
                self.assertFalse(aux.restore_locked(200))
                self.assertTrue(main.restore_locked(200))
                self.assertEqual(data.document['model'], before['model'])
                self.assertTrue(aux.needs_restoration_locked())
                self.assertTrue(aux.report(201)['groups']['aux:approval']['active'])
                self.assertEqual(aux.report(201)['compatibility']['reasons'], ['auxiliary_symbol'])
                aux.compatible = qualified
                self.assertTrue(aux.restore_locked(300))
                self.assertEqual(data.document, before)
