"""Dependency pin and narrowly admitted metadata-only native proof seams."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class AdvancedProofTests(unittest.TestCase):
    def test_installed_dependency_is_pinned_and_precedes_qualification(self):
        import s3_auto
        self.assertEqual(getattr(s3_auto, 'ADVANCED_REF', None), '13b2c1c9c8204bf333df240b2aacf98c3e6250b7')
        self.assertEqual(s3_auto.ADVANCED_VERSION, '1.1.0')
        calls = []
        class Run:
            advanced_manifest = {'ref': s3_auto.ADVANCED_REF, 'files': {'model_map.py': 'a' * 64}}
            def hermes(self, *args):
                calls.append(args)
                return type('Result', (), {'returncode': 0})()
            def json(self, source, **kwargs):
                if source == s3_auto.ADVANCED_CHECK:
                    calls.append(('attest', source))
                    return {'bytes_match': True, 'special': [], 'scan_on_install': True, 'verdict': 'safe'}
                calls.append(('readback', source))
                return {'version': '1.1.0', 'backend': 'model_map', 'loaded': True}
        result = s3_auto.install_advanced(Run())
        self.assertTrue(result['loaded'])
        self.assertIn('--ref', calls[0])
        self.assertIn(s3_auto.ADVANCED_REF, calls[0])
        self.assertEqual(calls[1][0], 'attest')
        self.assertEqual(calls[2], ('plugins', 'enable', 'advanced-delegation'))
        self.assertEqual(calls[3][0], 'readback')

    def test_dependency_rejected_before_enable_on_tree_or_scan_failure(self):
        import s3_auto
        from unittest import mock
        for field, value in (('bytes_match', False), ('special', ['link']), ('verdict', 'unsafe')):
            with self.subTest(field=field):
                calls = []
                class Run:
                    advanced_manifest = {'ref': s3_auto.ADVANCED_REF, 'files': {'model_map.py': 'a' * 64}}
                    def hermes(self, *args):
                        calls.append(args)
                    def json(self, source, *args, **kwargs):
                        result = {'bytes_match': True, 'special': [], 'verdict': 'safe', 'scan_on_install': True,
                                  'version': '1.1.0', 'backend': 'model_map', 'loaded': True}
                        result[field] = value
                        return result
                with self.assertRaises(s3_auto.Failure):
                    s3_auto.install_advanced(Run())
                self.assertFalse(any('enable' in call for call in calls))

    def test_dependency_inventory_checks_real_bytes_and_symlinks(self):
        import hashlib
        probe = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as home:
            root = Path(home)
            (root / 'model_map.py').write_text('synthetic')
            expected = {'model_map.py': hashlib.sha256(b'synthetic').hexdigest()}
            self.assertTrue(probe.dependency_inventory(root, expected)['bytes_match'])
            (root / 'model_map.py').write_text('changed')
            self.assertFalse(probe.dependency_inventory(root, expected)['bytes_match'])
            (root / 'linked').symlink_to(root / 'model_map.py')
            self.assertEqual(probe.dependency_inventory(root, expected)['special'], ['linked'])

    def test_metadata_admission_is_exact_and_never_admits_inference(self):
        probe = importlib.import_module('s3_native_consumers')
        with tempfile.TemporaryDirectory() as home:
            guard = probe.ProbeGuard(home)
            self.assertTrue(hasattr(guard, 'metadata_address'), 'metadata-only loopback admission missing')
            guard.metadata_address = ('127.0.0.1', 31415)
            for event, args in [('socket.connect', (None, ('127.0.0.1', 31416))),
                                ('socket.connect', (None, ('127.0.0.2', 31415))),
                                ('socket.getaddrinfo', ('example.test', 31415)),
                                ('urllib.Request', ('http://127.0.0.1:31415/v1/chat/completions', None, {}, 'POST')),
                                ('http.client.send', (None, b'POST /v1/chat/completions HTTP/1.1\r\n')),
                                ('http.client.send', (None, b'GET /private HTTP/1.1\r\n'))]:
                with self.subTest(event=event, args=args), self.assertRaises(probe.UnsafeProbe):
                    guard.audit(event, args)
            guard.audit('socket.connect', (None, ('127.0.0.1', 31415)))
            guard.audit('urllib.Request', ('http://127.0.0.1:31415/v1/models', None, {}, 'GET'))
            guard.audit('http.client.send', (None, b'GET /models-dev.json HTTP/1.1\r\n'))

    def test_external_plugin_sources_stay_confined_to_the_copied_dependency(self):
        probe = importlib.import_module('s3_native_consumers')
        self.assertTrue(hasattr(probe.NativeHost, 'plugin_function'), 'native external source attestation missing')
        with tempfile.TemporaryDirectory() as home:
            file = Path(home) / 'model_map.py'
            file.write_text('def route_task():\n    return {}\n')
            from importlib import util
            spec = util.spec_from_file_location('hqr_external_fixture', file)
            module = util.module_from_spec(spec)
            spec.loader.exec_module(module)
            native = object.__new__(probe.NativeHost)
            native.sources = {}
            native.plugin_root = Path(home)
            native.plugin_function(module.route_task)
            self.assertIn('hqr_external_fixture.route_task', native.sources)
            native.plugin_root = Path(home) / 'different'
            with self.assertRaises(probe.ProbeFailure):
                native.plugin_function(module.route_task)


if __name__ == '__main__':
    unittest.main()
