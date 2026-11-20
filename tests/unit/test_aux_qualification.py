# decisions/aux-plan.md, AUXP-03/04: qualification loss suspends transactions, never supplies a missing baseline.
"""Real Engine transitions with synthetic backends and changing qualification only."""
import copy
from pathlib import Path
import tempfile
import unittest

from quota_router.apply import Engine, locked_pair
from s3_fakes import Backend, TARGET, qualified

AUX = {'provider': 'anthropic', 'model': 'claude-sonnet-5-5'}


class QualificationSuspensionTests(unittest.TestCase):
    def test_drift_at_each_check_suspends_main_and_auxiliary_without_false_completion(self):
        for kind in ('main', 'auxiliary'):
            for failed_check in range(2, 6):
                with self.subTest(kind=kind, failed_check=failed_check), tempfile.TemporaryDirectory() as root:
                    data = Backend()
                    data.document['auxiliary'] = {'approval': {'provider': 'openai-codex', 'model': 'gpt-6.1-terra'}}
                    before = copy.deepcopy(data.document)
                    main = Engine(root, data, qualified)
                    aux = Engine(root, data, qualified, kind='auxiliary', state_name='aux-state.json', journal_name='aux-journal.json')
                    engine = main if kind == 'main' else aux
                    role, selection = ('conversation', TARGET) if kind == 'main' else ('aux:approval', AUX)
                    calls = []
                    def changing():
                        calls.append(True)
                        return {'ok': False, 'reasons': ['synthetic_drift']} if len(calls) >= failed_check else qualified()
                    engine.compatible = changing
                    with locked_pair(main, aux):
                        state_before = copy.deepcopy(engine.state)
                        records_before = {p.name: p.read_bytes() for p in Path(root).glob('*.json')}
                        self.assertIs(engine.cycle_locked({role: selection}, 100), False)
                        self.assertEqual(len(calls), failed_check)
                        self.assertEqual(engine.report(101)['compatibility']['reasons'], ['synthetic_drift'])
                        self.assertEqual(engine.state['generation'], 0)
                        self.assertEqual(engine.state['history'], [])
                        self.assertIsNone(engine.state['last_cycle'])
                        self.assertFalse(engine.state['auto_declared'])
                        if failed_check == 2:
                            self.assertEqual(engine.state, state_before)
                            self.assertEqual({p.name: p.read_bytes() for p in Path(root).glob('*.json')}, records_before)
                        if failed_check <= 4:
                            self.assertEqual(data.document, before)
                            self.assertEqual(data.writes, [])
                        else:
                            self.assertEqual(len(data.writes), 1)
                        self.assertEqual(bool(engine.read_record(engine.journal_name)), failed_check >= 4)
                        # Resume with qualification restored, retaining the original enrollment and any pending intent.
                        engine.compatible = qualified
                        engine.cycle_locked({role: selection}, 200)
                        self.assertEqual(engine.state['generation'], 1)
                        self.assertFalse(engine.read_record(engine.journal_name))
                        self.assertTrue(engine.restore_locked(300))
                        self.assertEqual(data.document, before)

    def test_drift_before_fallback_target_guard_stops_without_publishing_cycle(self):
        with tempfile.TemporaryDirectory() as root:
            data = Backend()
            calls = []
            def changing():
                calls.append(True)
                return qualified() if len(calls) < 3 else {'ok': False, 'reasons': ['synthetic_drift']}
            engine = Engine(root, data, changing)
            before = copy.deepcopy(data.document)
            self.assertIs(engine.cycle({'fallback:conversation': {'chain': []}}, 100), False)
            self.assertEqual(data.document, before)
            self.assertEqual(data.writes, [])
            self.assertIsNone(engine.state['last_cycle'])
            self.assertFalse(engine.state['auto_declared'])
            self.assertFalse((Path(root) / 'journal.json').exists())

    def test_qualification_loss_during_recovery_retains_intent_and_stops_cycle(self):
        with tempfile.TemporaryDirectory() as root:
            data = Backend()
            engine = Engine(root, data, qualified)
            with engine.locked():
                engine.cycle_locked({'conversation': TARGET}, 100)
                prior = engine.state['groups']['conversation']['baseline']
                target = engine.state['groups']['conversation']['last']
                data.document['model']['provider'] = prior['model.provider']['value']
                engine.persist(engine.journal_name, {'group': 'conversation', 'prior': prior, 'target': target, 'at': 200, 'restore': False})
            calls = []
            def changing():
                calls.append(True)
                return qualified() if len(calls) == 1 else {'ok': False, 'reasons': ['synthetic_drift']}
            engine.compatible = changing
            before = copy.deepcopy(data.document)
            records = {p.name: p.read_bytes() for p in Path(root).glob('*.json')}
            count = len(data.writes)
            self.assertIs(engine.cycle({'conversation': TARGET}, 300), False)
            self.assertEqual(data.document, before)
            self.assertEqual(len(data.writes), count)
            self.assertEqual({p.name: p.read_bytes() for p in Path(root).glob('*.json')}, records)
