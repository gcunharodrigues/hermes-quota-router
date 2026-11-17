# SOL-04 recovery contract: decisions/hqr-38-delivery.md, "publicação compatível autorizada".
"""Synthetic rollback interruptions and refusals; admitted test container only."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from test_sol04_persist_publish import fixture
from quota_router import downgrade, storage
from quota_router.apply import Engine


class Interrupted(Exception):
    pass


def stop_at(point):
    def checkpoint(name):
        if name == point:
            raise Interrupted(point)
    return checkpoint


def overwrite(path, raw):
    path.write_bytes(raw)
    path.chmod(0o600)


def records(engine):
    return {p.name: p.read_bytes() for p in engine.directory.iterdir() if p.is_file()}


class RecoveryTests(unittest.TestCase):
    def publish(self, engine, expected, **kwargs):
        return downgrade.publish_legacy_state(engine, expected, mode_reader=kwargs.pop('mode_reader', lambda: 'off'), **kwargs)

    def test_each_checkpoint_resumes_and_completion_is_idempotent(self):
        for point in ('backup_ready', 'intent_ready', 'before_publish', 'published', 'verified', 'completed'):
            with self.subTest(point=point), tempfile.TemporaryDirectory(prefix='sol04-resume-') as root:
                engine, backend, expected = fixture(root)
                before = backend.read(), copy.deepcopy(backend.writes)
                with self.assertRaisesRegex(Interrupted, point):
                    self.publish(engine, expected, checkpoint=stop_at(point))
                if point in ('intent_ready', 'before_publish', 'published', 'verified'):
                    for operation in (engine.begin, engine.recover, lambda: engine.restore(30), lambda: engine.cycle({}, 30)):
                        preserved = records(engine)
                        with self.assertRaisesRegex(ValueError, 'Pending legacy migration'):
                            operation()
                        self.assertEqual(records(engine), preserved)
                result = self.publish(Engine(engine.directory, backend, engine.compatible), expected)
                self.assertEqual(result['status'], 'complete')
                self.assertEqual((engine.directory / result['backup']).read_bytes(), expected)
                self.assertEqual((backend.read(), backend.writes), before)
                preserved = records(engine)
                self.assertEqual(self.publish(engine, expected)['status'], 'complete')
                self.assertEqual(records(engine), preserved)

    def test_configuration_change_between_attempts_is_not_a_new_reference(self):
        with tempfile.TemporaryDirectory(prefix='sol04-config-') as root:
            engine, backend, expected = fixture(root)
            with self.assertRaises(Interrupted):
                self.publish(engine, expected, checkpoint=stop_at('intent_ready'))
            before = records(engine)
            backend.document['agent']['reasoning_effort'] = 'low'
            human = backend.read()
            with self.assertRaisesRegex(ValueError, 'intention conflict'):
                self.publish(engine, expected)
            self.assertEqual(records(engine), before)
            self.assertEqual(backend.read(), human)

    def test_mode_or_configuration_change_immediately_before_publish_is_refused(self):
        for kind in ('mode', 'config'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='sol04-prepublish-') as root:
                engine, backend, expected = fixture(root)
                mode = ['off']
                def checkpoint(point):
                    if point == 'before_publish':
                        if kind == 'mode':
                            mode[0] = 'auto'
                        else:
                            backend.document['agent']['reasoning_effort'] = 'low'
                with self.assertRaises(ValueError):
                    self.publish(engine, expected, mode_reader=lambda: mode[0], checkpoint=checkpoint)
                self.assertEqual((engine.directory / 'state.json').read_bytes(), expected)
                self.assertEqual(json.loads((engine.directory / downgrade.MIGRATION).read_text())['phase'], 'pending')

    def test_reader_failure_preserves_pending_receipt_and_state(self):
        with tempfile.TemporaryDirectory(prefix='sol04-reader-') as root:
            engine, backend, expected = fixture(root)
            with self.assertRaises(Interrupted):
                self.publish(engine, expected, checkpoint=stop_at('intent_ready'))
            before = records(engine)
            with patch.object(backend, 'read', side_effect=OSError('synthetic reader failure')):
                with self.assertRaisesRegex(OSError, 'synthetic reader failure'):
                    self.publish(engine, expected)
            self.assertEqual(records(engine), before)

    def test_mode_and_qualification_are_required_before_backup(self):
        for kind in ('mode', 'qualification'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='sol04-admission-') as root:
                engine, backend, expected = fixture(root)
                if kind == 'qualification':
                    engine.compatible = lambda: {'ok': False}
                with self.assertRaises(ValueError):
                    self.publish(engine, expected, mode_reader=lambda: 'auto' if kind == 'mode' else 'off')
                self.assertEqual((engine.directory / 'state.json').read_bytes(), expected)
                self.assertFalse(list(engine.directory.glob('hqr38-rollback-*')))
                self.assertFalse((engine.directory / downgrade.MIGRATION).exists())

    def test_physically_present_falsy_auto_journal_is_not_absent(self):
        for value in (None, {}, [], False):
            with self.subTest(value=value), tempfile.TemporaryDirectory(prefix='sol04-journal-') as root:
                engine, backend, expected = fixture(root)
                overwrite(engine.directory / 'journal.json', json.dumps(value).encode())
                before = records(engine)
                with self.assertRaisesRegex(ValueError, 'Pending Auto journal'):
                    self.publish(engine, expected)
                self.assertEqual(records(engine), before)

    def test_falsy_or_malformed_migration_receipt_blocks_ordinary_engine(self):
        for value in (None, {}, [], False, {'phase': 'complete'}):
            with self.subTest(value=value), tempfile.TemporaryDirectory(prefix='sol04-marker-') as root:
                engine, backend, expected = fixture(root)
                overwrite(engine.directory / downgrade.MIGRATION, json.dumps(value).encode())
                before = records(engine)
                with self.assertRaises(ValueError):
                    engine.begin()
                self.assertEqual(records(engine), before)
                with self.assertRaises(ValueError):
                    self.publish(engine, expected)
                self.assertEqual(records(engine), before)

    def test_third_state_between_attempts_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix='sol04-third-') as root:
            engine, backend, expected = fixture(root)
            with self.assertRaises(Interrupted):
                self.publish(engine, expected, checkpoint=stop_at('intent_ready'))
            third = json.loads(expected)
            third['generation'] += 100
            overwrite(engine.directory / 'state.json', json.dumps(third).encode())
            before = records(engine)
            with self.assertRaisesRegex(ValueError, 'snapshot conflict'):
                self.publish(engine, expected)
            self.assertEqual(records(engine), before)

    def test_same_bytes_replacement_before_publish_is_detected(self):
        with tempfile.TemporaryDirectory(prefix='sol04-inode-') as root:
            engine, backend, expected = fixture(root)
            def checkpoint(point):
                if point == 'before_publish':
                    replacement = engine.directory / 'replacement.json'
                    overwrite(replacement, expected)
                    os.replace(replacement, engine.directory / 'state.json')
            with self.assertRaisesRegex(ValueError, 'publication target changed'):
                self.publish(engine, expected, checkpoint=checkpoint)
            self.assertEqual((engine.directory / 'state.json').read_bytes(), expected)

    def test_change_after_first_readback_cannot_be_marked_complete(self):
        with tempfile.TemporaryDirectory(prefix='sol04-final-readback-') as root:
            engine, backend, expected = fixture(root)
            third = json.loads(expected)
            third['generation'] += 100
            third_bytes = json.dumps(third).encode()
            def checkpoint(point):
                if point == 'verified':
                    overwrite(engine.directory / 'state.json', third_bytes)
            with self.assertRaises(ValueError):
                self.publish(engine, expected, checkpoint=checkpoint)
            self.assertEqual((engine.directory / 'state.json').read_bytes(), third_bytes)
            self.assertEqual(json.loads((engine.directory / downgrade.MIGRATION).read_text())['phase'], 'pending')

    def test_incomplete_backup_is_retained_without_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='sol04-backup-') as root:
            engine, backend, expected = fixture(root)
            backup = engine.directory / ('hqr38-rollback-' + hashlib.sha256(expected).hexdigest() + '.json')
            overwrite(backup, b'incomplete')
            before = records(engine)
            with self.assertRaisesRegex(ValueError, 'backup differs'):
                self.publish(engine, expected)
            self.assertEqual(records(engine), before)

    def test_symlink_or_hardlinked_backup_cannot_be_used(self):
        for kind in ('symlink', 'hardlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='sol04-link-') as root:
                engine, backend, expected = fixture(root)
                target = Path(root) / 'outside-state.json'
                overwrite(target, b'synthetic canary')
                backup = engine.directory / ('hqr38-rollback-' + hashlib.sha256(expected).hexdigest() + '.json')
                if kind == 'symlink':
                    backup.symlink_to(target)
                else:
                    os.link(target, backup)
                with self.assertRaises(OSError):
                    self.publish(engine, expected)
                self.assertEqual(target.read_bytes(), b'synthetic canary')
                self.assertEqual((engine.directory / 'state.json').read_bytes(), expected)

    def test_readback_error_leaves_pending_and_resume_does_not_republish_target(self):
        with tempfile.TemporaryDirectory(prefix='sol04-readback-') as root:
            engine, backend, expected = fixture(root)
            real_snapshot = downgrade._snapshot
            calls = [0]
            def snapshot(fd, name):
                if name == 'state.json':
                    calls[0] += 1
                    if calls[0] == 3:
                        raise OSError('synthetic readback failure')
                return real_snapshot(fd, name)
            with patch.object(downgrade, '_snapshot', side_effect=snapshot):
                with self.assertRaisesRegex(OSError, 'synthetic readback failure'):
                    self.publish(engine, expected)
            self.assertEqual(json.loads((engine.directory / downgrade.MIGRATION).read_text())['phase'], 'pending')
            real_publish = storage.publish
            def publish(fd, name, value):
                if name == 'state.json':
                    raise AssertionError('Unnecessary state republication')
                return real_publish(fd, name, value)
            with patch.object(storage, 'publish', side_effect=publish):
                self.assertEqual(self.publish(engine, expected)['status'], 'complete')

    def test_receipt_directory_fsync_failure_is_not_success_or_early_release(self):
        with tempfile.TemporaryDirectory(prefix='sol04-fsync-') as root:
            engine, backend, expected = fixture(root)
            real_replace, real_fsync = os.replace, os.fsync
            renames, fail = [0], [False]
            def replace(src, dst, **kwargs):
                value = real_replace(src, dst, **kwargs)
                if dst == downgrade.MIGRATION:
                    renames[0] += 1
                    if renames[0] == 2:
                        fail[0] = True
                return value
            def fsync(fd):
                if fail[0] and stat.S_ISDIR(os.fstat(fd).st_mode):
                    raise OSError('synthetic directory fsync failure')
                return real_fsync(fd)
            with patch.object(os, 'replace', side_effect=replace), patch.object(os, 'fsync', side_effect=fsync):
                with self.assertRaisesRegex(OSError, 'synthetic directory fsync failure'):
                    self.publish(engine, expected)
                with self.assertRaisesRegex(OSError, 'synthetic directory fsync failure'):
                    with engine.locked():
                        self.fail('Engine released before successful directory sync')
            self.assertEqual(self.publish(engine, expected)['status'], 'complete')

    def test_unrelated_configuration_is_preserved_and_not_hashed_into_receipt(self):
        with tempfile.TemporaryDirectory(prefix='sol04-unowned-') as root:
            engine, backend, expected = fixture(root)
            backend.document['unowned'] = {'synthetic_secret': 'not-for-state-synthetic-marker'}
            with self.assertRaises(Interrupted):
                self.publish(engine, expected, checkpoint=stop_at('intent_ready'))
            backend.document['unowned']['additional'] = 'human edit'
            before = backend.read()
            self.assertEqual(self.publish(engine, expected)['status'], 'complete')
            self.assertEqual(backend.read(), before)
            for path in engine.directory.iterdir():
                if path.is_file():
                    self.assertNotIn(b'not-for-state-synthetic-marker', path.read_bytes())
