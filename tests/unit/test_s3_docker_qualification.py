"""Docker qualification is complete, location-free and selected by revision plus exact bytes."""
import copy
import json
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat

REVISION = '3b421578588243f920886e6fe79a6faa87ea026e'


class DockerQualificationTests(unittest.TestCase):
    def entry(self):
        entries = json.loads(compat.DATA.read_text())['hosts']
        docker = [entry for entry in entries if entry['label'].startswith('Docker hqr-s1-test;')]
        self.assertEqual(len(docker), 1, 'Docker source qualification entry missing')
        return docker[0]

    def test_docker_entry_has_complete_fingerprints_without_locations(self):
        entry = self.entry()
        self.assertEqual(entry['revision'], REVISION)
        self.assertEqual(entry['advanced_delegation'], {'version': '1.1.0', 'ref': '13b2c1c9c8204bf333df240b2aacf98c3e6250b7'})
        self.assertFalse(entry['session_store_qualified'])
        self.assertEqual(entry['hooks_qualified'], [])
        # HQR-38 installed recovery: the Docker source was measured; pending copies must still fail closed.
        self.assertFalse(entry.get('requalification_required'))
        for kind, specs in (('functions', compat.FUNCTIONS), ('constants', compat.CONSTANTS)):
            required = {module + '.' + name for module, names in specs.items() for name in names}
            self.assertEqual(set(entry[kind]), required)
            self.assertTrue(all(value is not None for value in entry[kind].values()))
        self.assertEqual(len(entry['functions']), 152)
        self.assertEqual(len(entry['constants']), 19)
        self.assertTrue(all(re.fullmatch('[a-f0-9]{64}', value) for value in entry['functions'].values()))
        self.assertNotIn('/home/', json.dumps(entry))
        self.assertNotIn('/opt/', json.dumps(entry))

    def test_docker_selection_requires_exact_revision_and_every_fingerprint(self):
        # Exercise the measured entry, not a fixture completed from another host's fingerprints.
        entry = copy.deepcopy(self.entry())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.git').mkdir()
            (root / '.git/HEAD').write_text(REVISION + '\n')
            data = root / 'hosts.json'
            data.write_text(json.dumps({'hosts': [entry]}))
            backend = types.ModuleType('hermes_cli.config_backend')
            backend.__file__ = str(root / 'hermes_cli/config_backend.py')
            constants = types.ModuleType('hermes_constants')
            constants.get_hermes_home = lambda: root / 'relocated-home'
            symbols = {kind: copy.deepcopy(entry[kind]) for kind in ('functions', 'constants')}
            with mock.patch.dict(sys.modules, {'hermes_cli.config_backend': backend, 'hermes_constants': constants}), \
                    mock.patch.object(compat, 'DATA', data), \
                    mock.patch.object(compat, 'collect_symbols', return_value=symbols), \
                    mock.patch.dict('os.environ', {'HERMES_CONFIG_BACKEND': 'file'}):
                result = compat._source_compatibility()
                self.assertTrue(result['ok'], result)
                self.assertEqual(result['host'], entry['label'])
                self.assertEqual(result['revision'], REVISION)
                (root / '.git/HEAD').write_text('b' * 40 + '\n')
                self.assertEqual(compat._source_compatibility()['reasons'], ['host_not_qualified'])
                (root / '.git/HEAD').write_text(REVISION + '\n')
                for kind in ('functions', 'constants'):
                    for key in symbols[kind]:
                        with self.subTest(kind=kind, symbol=key):
                            original = symbols[kind][key]
                            symbols[kind][key] = None
                            self.assertEqual(compat._source_compatibility()['reasons'], [key])
                            symbols[kind][key] = original
                (root / '.git/HEAD').unlink()
                result = compat._source_compatibility()
                if entry.get('allow_revisionless_match') is True:
                    self.assertTrue(result['ok'], result)
                    self.assertIsNone(result['revision'])
                else:
                    self.assertFalse(result['ok'], result)
