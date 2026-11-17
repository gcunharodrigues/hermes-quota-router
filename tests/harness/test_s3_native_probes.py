"""Hermetic contracts for native probes; no host imports, Docker or account reader."""
import importlib
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class NativeProbeContracts(unittest.TestCase):
    def probe(self):
        try:
            return importlib.import_module('s3_native_consumers')
        except ModuleNotFoundError:
            self.fail('native consumer probe module is missing')

    def test_model_config_decoding_is_strict(self):
        probe = self.probe()
        route = {'model': 'test-model', 'provider': 'anthropic'}
        self.assertEqual(probe.decode_model_config(route), route)
        self.assertEqual(probe.decode_model_config('{"model":"test-model","provider":"anthropic"}'), route)
        for value in (None, [], '[]', '{broken', 'null', 42):
            with self.subTest(value=value), self.assertRaises(probe.ProbeFailure):
                probe.decode_model_config(value)

    def test_gate_requires_every_scenario_and_does_not_trust_pending_list(self):
        probe = self.probe()
        report = {'scenarios': {name: {'pass': True} for name in probe.REQUIRED}, 'pending_consumer_proofs': []}
        probe.require_complete(report)
        for name in probe.REQUIRED:
            bad = {**report, 'scenarios': {k: v for k, v in report['scenarios'].items() if k != name}}
            with self.subTest(name=name), self.assertRaises(probe.ProbeFailure):
                probe.require_complete(bad)
        report['scenarios']['C4'] = {'pass': False, 'reason': 'native backend unavailable'}
        with self.assertRaisesRegex(probe.ProbeFailure, 'C4.*native backend unavailable'):
            probe.require_complete(report)

    def test_absence_projection_ignores_only_native_lifecycle_lists(self):
        import copy
        import s3_auto
        baseline = {'model': {'provider': 'anthropic'}, 'plugins': {'enabled': [s3_auto.PLUGIN],
                    'entries': {s3_auto.PLUGIN: {'settings': {'mode': 'auto'}}}}}
        disabled = copy.deepcopy(baseline)
        disabled['plugins']['enabled'] = []
        disabled['plugins']['disabled'] = [s3_auto.PLUGIN]
        self.assertEqual(s3_auto.absence_projection(baseline), s3_auto.absence_projection(disabled))
        disabled['model']['provider'] = 'openai-codex'
        self.assertNotEqual(s3_auto.absence_projection(baseline), s3_auto.absence_projection(disabled))

    def test_review_gate_includes_jobs_error_and_removal_proofs(self):
        probe = self.probe()
        self.assertTrue({'C8', 'C9', 'C12', 'E2'} <= set(probe.REQUIRED))
        report = {'scenarios': {name: {'pass': True} for name in probe.REQUIRED}}
        for name in ('C8', 'C9', 'C12', 'E2'):
            with self.subTest(name=name), self.assertRaises(probe.ProbeFailure):
                probe.require_complete({'scenarios': {k: v for k, v in report['scenarios'].items() if k != name}})

    def test_product_removal_refuses_declared_auto_without_native_remove_call(self):
        import s3_auto
        self.assertTrue(hasattr(s3_auto, 'require_removable'))
        for state in ({'mode_saved': 'auto', 'mode_effective': 'unavailable'},
                      {'mode_saved': 'off', 'mode_effective': 'off', 'applied': {'auto_declared': True}},
                      {'mode_saved': 'off', 'mode_effective': 'off', 'applied': {'groups': {'general': {'active': True}}}}):
            state = dict({'ok': True}, **state)
            calls = []
            class Run:
                def probe(self, *_args):
                    return {'results': [{'result': state, 'watched_events': []}]}
                def hermes(self, *args):
                    calls.append(args)
            with self.subTest(state=state), self.assertRaises(s3_auto.Failure):
                s3_auto.product_remove(Run())
            self.assertEqual(calls, [])
        s3_auto.require_removable({'ok': True, 'mode_saved': 'off', 'mode_effective': 'off', 'applied': {'auto_declared': False}})

    def test_trace_stops_before_native_boundary_without_faking_result(self):
        probe = self.probe()
        entered = []
        def transport(model, requested):
            entered.append(True)
            raise AssertionError('must not authenticate')
        def native_tick():
            return transport(model='chosen', requested='anthropic')
        previous = sys.gettrace()
        found = probe.stop_at_call(native_tick, transport)
        self.assertEqual(found['callee'], {'model': 'chosen', 'requested': 'anthropic'})
        self.assertEqual(entered, [])
        self.assertIs(sys.gettrace(), previous)
        with self.assertRaisesRegex(probe.ProbeFailure, 'boundary not reached'):
            probe.stop_at_call(lambda: None, transport)
        self.assertIs(sys.gettrace(), previous)

    def test_mutable_source_cannot_be_qualified_by_a_matching_route(self):
        probe = self.probe()
        verdict = probe.source_verdict(started_stable=True, model_config_immutable=False, capture_order=True)
        self.assertFalse(verdict['qualified'])
        self.assertIn('model_config_mutable', verdict['reasons'])
        self.assertFalse(probe.source_verdict(started_stable=True, model_config_immutable=True, capture_order=False)['qualified'])
        self.assertTrue(probe.source_verdict(started_stable=True, model_config_immutable=True, capture_order=True)['qualified'])


if __name__ == '__main__':
    unittest.main()
