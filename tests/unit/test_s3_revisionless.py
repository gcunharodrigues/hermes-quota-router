"""HQR-26: complete fingerprint binding for explicitly qualified release-tarball hosts."""
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat


class RevisionlessTests(unittest.TestCase):
    @contextmanager
    def host(self, *, allow=True):
        entry = copy.deepcopy(json.loads(compat.DATA.read_text())['hosts'][0])
        entry['allow_revisionless_match'] = allow
        symbols = {kind: copy.deepcopy(entry[kind]) for kind in ('functions', 'constants')}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'hosts.json'
            data.write_text(json.dumps({'hosts': [entry]}))
            backend = types.ModuleType('hermes_cli.config_backend')
            backend.__file__ = str(root / 'hermes_cli/config_backend.py')
            constants = types.ModuleType('hermes_constants')
            constants.get_hermes_home = lambda: root / 'synthetic-home'
            with mock.patch.dict(sys.modules, {'hermes_cli.config_backend': backend, 'hermes_constants': constants}), \
                    mock.patch.object(compat, 'DATA', data), \
                    mock.patch.object(compat, 'collect_symbols', return_value=symbols), \
                    mock.patch.dict('os.environ', {'HERMES_CONFIG_BACKEND': 'file'}):
                yield root, entry, symbols, data

    def test_revisionless_complete_fingerprint_match_qualifies(self):
        with self.host():
            result = compat._source_compatibility()
        self.assertTrue(result['ok'], result)
        self.assertIsNone(result['revision'])
        self.assertEqual(result['revision_note'], 'revisão do Hermes não identificada; impressões conferem')

    def test_revisionless_status_discloses_missing_revision_and_verified_fingerprints(self):
        from quota_router.lifecycle import Management
        from quota_router.mapping import approved_base
        from quota_router.render import render
        context = types.SimpleNamespace(get_config=lambda key, default=None: approved_base() if key == 'roles' else default)
        with self.host():
            manager = Management(context, profile=lambda: 'default', compatible=compat._source_compatibility)
            status = manager.status()
        self.assertTrue(status['auto_available'])
        self.assertEqual(status['compatibility'].get('revision_note'), 'revisão do Hermes não identificada; impressões conferem')
        self.assertIsNone(status['compatibility']['revision'])
        self.assertIn('revisão do Hermes não identificada; impressões conferem', render('status', status))

    def test_revisionless_function_or_constant_drift_suspends(self):
        with self.host() as (_, _, symbols, _):
            for kind in ('functions', 'constants'):
                for key in symbols[kind]:
                    with self.subTest(kind=kind, key=key):
                        original = symbols[kind][key]
                        symbols[kind][key] = None
                        result = compat._source_compatibility()
                        self.assertFalse(result['ok'], result)
                        self.assertEqual(result['reasons'], [key])
                        self.assertNotIn('revision_note', result)
                        symbols[kind][key] = original

    def test_revisionless_entry_requires_explicit_boolean_opt_in(self):
        for allow in (False, None, 'true', 1):
            with self.subTest(allow=allow), self.host(allow=allow):
                self.assertFalse(compat._source_compatibility()['ok'])
        with self.host() as (_, entry, _, data):
            del entry['allow_revisionless_match']
            data.write_text(json.dumps({'hosts': [entry]}))
            self.assertFalse(compat._source_compatibility()['ok'])

    def test_readable_mismatched_revision_never_uses_revisionless_opt_in(self):
        with self.host() as (root, entry, _, _):
            (root / '.git').mkdir()
            (root / '.git/HEAD').write_text('b' * 40 + '\n')
            self.assertNotEqual(entry['revision'], 'b' * 40)
            self.assertEqual(compat._source_compatibility()['reasons'], ['host_not_qualified'])
            (root / '.git/HEAD').write_text(entry['revision'] + '\n')
            result = compat._source_compatibility()
            self.assertTrue(result['ok'], result)
            self.assertEqual(result['revision'], entry['revision'])
            self.assertNotIn('revision_note', result)

    def test_partial_or_expanded_fingerprint_sets_never_qualify(self):
        for kind in ('functions', 'constants'):
            for side in ('entry', 'actual'):
                for action in ('missing', 'extra'):
                    with self.subTest(kind=kind, side=side, action=action), self.host() as (_, entry, symbols, data):
                        values = entry[kind] if side == 'entry' else symbols[kind]
                        if action == 'missing':
                            del values[next(iter(values))]
                        else:
                            values['unknown.extra'] = 'unreviewed'
                        data.write_text(json.dumps({'hosts': [entry]}))
                        self.assertFalse(compat._source_compatibility()['ok'])

    def test_changed_function_body_digest_suspends_revisionless_match(self):
        with self.host() as (_, _, symbols, _):
            key = next(iter(symbols['functions']))
            self.assertNotEqual(symbols['functions'][key], '0' * 64)
            symbols['functions'][key] = '0' * 64
            result = compat._source_compatibility()
        self.assertFalse(result['ok'], result)
        self.assertEqual(result['reasons'], [key])

    def test_docker_entry_explicitly_allows_revisionless_tarball_with_public_provenance(self):
        entries = json.loads(compat.DATA.read_text())['hosts']
        entry = next(host for host in entries if host['label'].startswith('Docker hqr-s1-test;'))
        self.assertIs(entry.get('allow_revisionless_match'), True)
        self.assertEqual(entry.get('source_provenance'), {
            'recipe': 'tests/installed/Dockerfile',
            'image_label': {'hqr.host': '3b421578588243f920886e6fe79a6faa87ea026e'},
            'tarball_sha256': '2525046f165880c22f177f2214c8da3e26c58cb0aeab5bd09aad940556538897',
        })

    def test_partial_entries_cannot_combine_into_complete_qualification(self):
        with self.host() as (_, entry, _, data):
            other = copy.deepcopy(entry)
            del entry['functions'][next(iter(entry['functions']))]
            del other['constants'][next(iter(other['constants']))]
            data.write_text(json.dumps({'hosts': [entry, other]}))
            self.assertFalse(compat._source_compatibility()['ok'])
