# SOL-04: decisions/hqr-38-delivery.md, "publicação compatível autorizada".
"""Synthetic, explicit rollback publication; execute only in the admitted test container."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from s3_fakes import Backend, TARGET, qualified
from quota_router import downgrade, storage
from quota_router.apply import Engine

CHAIN = [{'provider': 'anthropic', 'model': 'claude-opus-5-5'}]


def fixture(root):
    backend = Backend()
    baseline = backend.read()
    engine = Engine(Path(root) / 'state', backend, qualified)
    engine.cycle({'conversation': TARGET, 'fallback:conversation': {'chain': CHAIN}}, 10)
    if engine.restore(20) is not True:
        raise AssertionError('Fixture OFF failed')
    expected = (engine.directory / 'state.json').read_bytes()
    if backend.read() != baseline:
        raise AssertionError('Fixture baseline not restored')
    return engine, backend, expected


class PublishRollbackTests(unittest.TestCase):
    def test_exact_backup_compatible_publication_and_idempotent_completion(self):
        with tempfile.TemporaryDirectory(prefix='sol04-publish-') as root:
            engine, backend, expected = fixture(root)
            original = json.loads(expected)
            config_before, writes_before = backend.read(), copy.deepcopy(backend.writes)
            result = downgrade.publish_legacy_state(engine, expected, mode_reader=lambda: 'off')
            self.assertEqual(result['status'], 'complete')
            self.assertEqual((engine.directory / result['backup']).read_bytes(), expected)
            published = (engine.directory / 'state.json').read_bytes()
            self.assertEqual(json.loads(published), downgrade.prepare_legacy_state(original, mode='off', journal=None))
            self.assertEqual(json.loads(published)[downgrade.ARCHIVE]['source_state'], original)
            receipt = json.loads((engine.directory / downgrade.MIGRATION).read_text())
            self.assertEqual(receipt['phase'], 'complete')
            self.assertEqual((backend.read(), backend.writes), (config_before, writes_before))
            # A repeated reconciliation verifies success; it cannot republish or nest the archive.
            with patch.object(storage, 'publish', side_effect=AssertionError('Repeated publication')):
                repeated = downgrade.publish_legacy_state(engine, expected, mode_reader=lambda: 'off')
            self.assertEqual(repeated['status'], 'complete')
            self.assertEqual((engine.directory / 'state.json').read_bytes(), published)
            self.assertEqual(len(list(engine.directory.glob('hqr38-rollback-*.json'))), 1)
            with engine.locked():
                self.assertEqual(engine.state, json.loads(published))
