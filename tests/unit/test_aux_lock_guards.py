# decisions/aux-plan.md, AUXP-04: named records must not overwrite the global migration gate.
import json
from pathlib import Path
import tempfile
import unittest

from quota_router.apply import Engine, durable, locked_pair
from s3_fakes import Backend, qualified


class AuxiliaryLockGuardTests(unittest.TestCase):
    def test_record_names_cannot_alias_migration_receipts_or_backups(self):
        for name in ('hqr38-downgrade.json', 'hqr38-rollback-' + 'a' * 64 + '.json'):
            for field in ('state_name', 'journal_name'):
                with self.subTest(name=name, field=field), tempfile.TemporaryDirectory() as root:
                    args = dict(kind='auxiliary', state_name='aux-state.json', journal_name='aux-journal.json')
                    args[field] = name
                    with self.assertRaises(ValueError):
                        Engine(root, Backend(), qualified, **args)

    def test_pending_main_migration_blocks_pair_before_any_auxiliary_write(self):
        with tempfile.TemporaryDirectory() as root:
            data = Backend()
            main = Engine(root, data, qualified)
            aux = Engine(root, data, qualified, kind='auxiliary', state_name='aux-state.json', journal_name='aux-journal.json')
            durable(Path(root) / 'hqr38-downgrade.json', {'schema': 1, 'purpose': 'hqr38_legacy_downgrade', 'phase': 'pending',
                    'source_sha256': 'a' * 64, 'target_sha256': 'b' * 64, 'config_sha256': 'c' * 64,
                    'backup': 'hqr38-rollback-' + 'a' * 64 + '.json'})
            before = {p.name: p.read_bytes() for p in Path(root).glob('*.json')}
            with self.assertRaises(ValueError):
                with locked_pair(main, aux):
                    self.fail('migration gate must precede both engines')
            self.assertEqual({p.name: p.read_bytes() for p in Path(root).glob('*.json')}, before)
            self.assertEqual(data.writes, [])
            self.assertIsNone(main._directory_fd)
            self.assertIsNone(aux._directory_fd)

    def test_auxiliary_is_not_coupled_to_subagent_availability(self):
        with tempfile.TemporaryDirectory() as root:
            data = Backend()
            data.document['auxiliary'] = {'approval': {'provider': 'openai-codex', 'model': 'gpt-6.1-terra'}}
            main = Engine(root, data, qualified)
            aux = Engine(root, data, lambda: {'ok': True, 'subagents': {'ok': False}},
                         kind='auxiliary', state_name='aux-state.json', journal_name='aux-journal.json')
            with locked_pair(main, aux):
                aux.cycle_locked({'aux:approval': {'provider': 'anthropic', 'model': 'claude-sonnet-5-5'}}, 100)
                self.assertEqual(data.document['auxiliary']['approval']['provider'], 'anthropic')
                self.assertEqual(aux.report(100)['groups_out'], {})
