"""Filesystem boundary regressions with synthetic files only."""
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

from quota_router.apply import Engine
from s3_fakes import Backend, TARGET, qualified


class StorageReviewTests(unittest.TestCase):
    def test_symlinked_data_directory_is_rejected_before_state_or_backend_write(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            outside = root / 'outside'
            outside.mkdir(mode=0o700)
            directory = root / 'data'
            directory.symlink_to(outside, target_is_directory=True)
            backend = Backend()
            with self.assertRaises(OSError):
                Engine(directory, backend, qualified).cycle({'conversation': TARGET}, 100)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertEqual(backend.writes, [])

    def test_symlinked_lock_is_rejected_without_chmod_of_target(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            outside = root / 'outside'
            outside.write_text('unchanged')
            outside.chmod(0o644)
            directory = root / 'data'
            directory.mkdir(mode=0o700)
            (directory / 'auto.lock').symlink_to(outside)
            backend = Backend()
            with self.assertRaises(OSError):
                Engine(directory, backend, qualified).cycle({'conversation': TARGET}, 100)
            self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o644)
            self.assertEqual(outside.read_text(), 'unchanged')
            self.assertEqual(backend.writes, [])

    def test_permissive_data_root_and_writable_ancestor_are_rejected(self):
        for ancestor in (False, True):
            with self.subTest(ancestor=ancestor), tempfile.TemporaryDirectory() as root:
                parent = Path(root) / 'parent'
                parent.mkdir(mode=0o700)
                directory = parent / 'data'
                directory.mkdir(mode=0o700)
                (parent if ancestor else directory).chmod(0o777 if ancestor else 0o755)
                backend = Backend()
                with self.assertRaises(OSError):
                    Engine(directory, backend, qualified).cycle({'conversation': TARGET}, 100)
                self.assertEqual(list(directory.iterdir()), [])
                self.assertEqual(backend.writes, [])

    def test_default_storage_path_is_created_privately_without_native_mkdir_helper(self):
        import sys
        import types
        from unittest import mock
        from test_s3_lifecycle import AutoContext
        from quota_router.lifecycle import Management
        from quota_router.mapping import approved_base
        from s2_fakes import NOW, codex, claude, reader_for
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            constants = types.ModuleType('hermes_constants')
            constants.get_hermes_home = lambda: root
            native_storage = types.ModuleType('plugins.plugin_storage')
            native_storage.plugin_data_dir = mock.Mock(side_effect=AssertionError('Native helper creates permissive dirs'))
            backend = Backend()
            with mock.patch.dict(sys.modules, {'hermes_constants': constants, 'plugins.plugin_storage': native_storage}):
                manager = Management(AutoContext({'roles': approved_base()}), backend=backend, compatible=qualified,
                                     sources=lambda: (backend.read(), []), profile=lambda: 'default', clock=lambda: NOW,
                                     importer=lambda: reader_for(openai_codex=codex(100), anthropic=claude(10)), catalogs=lambda: {})
                self.addCleanup(manager.close)
                result = json.loads(manager.command('mode auto --json'))
                self.assertTrue(result['ok'], result)
            native_storage.plugin_data_dir.assert_not_called()
            self.assertEqual(stat.S_IMODE(manager.data_dir.stat().st_mode), 0o700)

    def test_state_symlinks_and_special_records_are_rejected(self):
        for kind in ('state', 'fifo'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as root:
                root = Path(root)
                directory = root / 'data'
                directory.mkdir(mode=0o700)
                outside = root / 'external'
                outside.write_text('{}')
                if kind == 'state':
                    (directory / 'state.json').symlink_to(outside)
                else:
                    os.mkfifo(directory / 'state.json', 0o600)
                backend = Backend()
                with self.assertRaises(OSError):
                    Engine(directory, backend, qualified).cycle({'conversation': TARGET}, 100)
                self.assertEqual(backend.writes, [])
                self.assertEqual(outside.read_text(), '{}')
