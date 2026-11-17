"""Reviewed public manifest passes install attestation; a tampered copy never reaches enable."""
import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))
MANIFEST = Path(__file__).resolve().parents[1] / 'installed/advanced-delegation-13b2c1c.json'


class ReviewedManifestTests(unittest.TestCase):
    def manifest(self):
        self.assertTrue(MANIFEST.is_file(), 'reviewed public dependency byte manifest missing')
        return json.loads(MANIFEST.read_text())

    def test_checked_in_manifest_has_pinned_public_tree_and_runner_accepts_it(self):
        runner = importlib.import_module('s3_auto')
        expected = self.manifest()
        self.assertEqual(set(expected), {'ref', 'files'})
        self.assertEqual(expected['ref'], runner.ADVANCED_REF)
        self.assertEqual(len(expected['files']), 23)
        self.assertEqual(expected['files']['plugin.yaml'], '71d4bd26cb71e353d71cd04db9d5ea4955b013b139bc51ff94d831b77dd4b938')
        self.assertTrue(all(not Path(name).is_absolute() and '..' not in Path(name).parts for name in expected['files']))
        run = self.run_fixture(expected, expected)
        result = runner.install_advanced(run)
        self.assertEqual(result['version'], runner.ADVANCED_VERSION)
        self.assertEqual([call[1] for call in run.calls], ['install', 'enable'])

    @staticmethod
    def run_fixture(supplied, actual):
        runner = importlib.import_module('s3_auto')
        class Run:
            advanced_manifest = supplied
            calls = None
            def __init__(self):
                self.calls = []
            def hermes(self, *args):
                self.calls.append(args)
            def json(self, script, **kwargs):
                if script == runner.ADVANCED_CHECK:
                    checked = json.loads(kwargs['stdin'])
                    return {'bytes_match': checked['files'] == actual['files'], 'special': [], 'scan_on_install': True, 'verdict': 'safe'}
                return {'version': runner.ADVANCED_VERSION, 'backend': 'model_map'}
        return Run()

    def test_tampered_manifest_copy_is_rejected_before_enable(self):
        runner = importlib.import_module('s3_auto')
        reviewed = self.manifest()
        tampered = copy.deepcopy(reviewed)
        tampered['files']['model_map.py'] = '0' * 64
        self.assertNotEqual(tampered, reviewed)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tampered.json'
            path.write_text(json.dumps(tampered))
            run = self.run_fixture(json.loads(path.read_text()), reviewed)
            with self.assertRaisesRegex(runner.Failure, 'tree or scan policy differs'):
                runner.install_advanced(run)
            self.assertEqual([call[1] for call in run.calls], ['install'])
