"""Native probe safety, receipts and installed-runner wiring without a Hermes import."""
import importlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/installed'))


class ExecutionContracts(unittest.TestCase):
    def module(self):
        return importlib.import_module('s3_native_consumers')

    def test_probe_guard_rejects_network_credentials_and_foreign_config(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'ProbeGuard'), 'native probe audit guard missing')
        with tempfile.TemporaryDirectory() as directory:
            guard = module.ProbeGuard(directory)
            for event, args in [('socket.connect', (None, ('127.0.0.1', 1))), ('socket.getaddrinfo', ('test', 443)),
                                ('subprocess.Popen', ('python', ['python', '-c', 'pass'], None, None)),
                                ('open', (directory + '/auth.json', 'r', 0)),
                                ('open', (directory + '/.env', 'r', 0)), ('open', ('/other/config.yaml', 'r', 0)),
                                ('open', ('/other/state.db', 'r', 0)), ('open', ('/other/write.txt', 'w', 0))]:
                with self.subTest(event=event, args=args), self.assertRaises(module.UnsafeProbe):
                    guard.audit(event, args)
            guard.audit('open', (directory + '/config.yaml', 'r', 0))
            guard.audit('open', (directory + '/probe.db', 'w', 0))
            self.assertEqual(len(guard.denied), 8)

    def test_route_assertion_checks_all_three_fields(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'check_route'), 'native route comparator missing')
        route = {'provider': 'anthropic', 'model': 'claude-opus-5-5', 'effort': 'high'}
        self.assertEqual(module.check_route(route, route), route)
        for field in route:
            with self.subTest(field=field), self.assertRaises(module.ProbeFailure):
                module.check_route({**route, field: 'different'}, route)
        with self.assertRaises(module.ProbeFailure):
            module.check_route({'provider': 'anthropic', 'model': 'claude-opus-5-5'}, route)

    def test_failed_native_case_remains_an_explicit_gate(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'case'), 'native case recorder missing')
        def fail():
            raise module.ProbeFailure('native backend missing')
        result = module.case(fail)
        self.assertEqual(result, {'pass': False, 'reason': 'native backend missing'})
        self.assertEqual(module.case(lambda: {'boundary': 'native'}), {'pass': True, 'observed': {'boundary': 'native'}})

    def test_ac22_unqualified_fallback_is_exercised_not_just_declared(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'check_fallback'), 'AC-22 fallback assertion missing')
        from quota_router import events
        observed = module.check_fallback(events, {'qualified': False, 'reasons': ['model_config_mutable']})
        self.assertEqual(set(observed), {'delayed_A1_B_A2', 'capture_inside_window', 'changed_model', 'unknown_parent'})
        self.assertTrue(all(item == {'state': 'geração indeterminada'} for item in observed.values()))
        class WrongEvents:
            native_evidence = staticmethod(lambda *_: {'qualified': False})
            generation_for = staticmethod(lambda *_: {'state': 'qualified', 'age_s': 1})
        with self.assertRaises(module.ProbeFailure):
            module.check_fallback(WrongEvents, {'qualified': False})

    def test_installed_script_embeds_native_probe_and_runs_it_around_apply(self):
        import s3_auto
        self.assertTrue(hasattr(s3_auto, 'NATIVE_SOURCE'), 'installed runner does not ship the native probe')
        self.assertIn('class ConsumerProbe', s3_auto.NATIVE_SOURCE)
        self.assertLess(s3_auto.EXERCISE.index('ConsumerProbe'), s3_auto.EXERCISE.index("auto = command('mode auto')"))
        self.assertIn('consumers.after(', s3_auto.EXERCISE)
        self.assertNotIn("['C1-C6-native-session-lifecycle'", s3_auto.EXERCISE)


if __name__ == '__main__':
    unittest.main()
