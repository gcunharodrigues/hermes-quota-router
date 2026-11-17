"""Admission-only performs Docker inspection and never reaches product commands or probes."""
import copy
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class AdmissionOnlyTests(unittest.TestCase):
    def target(self):
        runner = importlib.import_module('s3_auto')
        return {'Id': 'synthetic-container', 'Config': {'User': '10001:10001', 'Labels': {'hqr.task': runner.TASK_LABEL}},
            'HostConfig': {'CapDrop': ['ALL'], 'CapAdd': [], 'Privileged': False, 'NetworkMode': 'bridge',
                'PortBindings': {}, 'PublishAllPorts': False, 'SecurityOpt': ['no-new-privileges=true'],
                'PidMode': '', 'IpcMode': 'private', 'Binds': [runner.VOLUME + ':' + runner.STATE]},
            'NetworkSettings': {'Networks': {'bridge': {}}},
            'Mounts': [{'Type': 'volume', 'Name': runner.VOLUME, 'Destination': runner.STATE, 'Driver': 'local', 'RW': True}]}

    def invoke(self, info, listeners=None):
        runner = importlib.import_module('s3_auto')
        calls, steps = [], []
        volume = {'Driver': 'local', 'Options': {}, 'Labels': {'hqr.task': runner.TASK_LABEL}}
        class InspectOnlyRun:
            def __init__(self, _receipts):
                pass
            def docker(self, *args):
                calls.append(args)
                if args == ('inspect', runner.TARGET):
                    return types.SimpleNamespace(stdout=json.dumps([info]))
                if args == ('volume', 'inspect', runner.VOLUME):
                    return types.SimpleNamespace(stdout=json.dumps([volume]))
                raise AssertionError('Non-inspection Docker command reached')
            def step(self, name, function):
                steps.append(name)
                return function()
            def __getattr__(self, name):
                raise AssertionError('Product method accessed: ' + name)
        listener = mock.Mock(return_value={'tcp': [], 'udp': []}, side_effect=listeners)
        with mock.patch.object(runner, 'S2Run', InspectOnlyRun), mock.patch.object(runner, 'listener_admission', listener):
            try:
                result = runner.main(['unused-receipts', '--candidate', 'a' * 40, '--rollback', 'b' * 40,
                    '--advanced-manifest', str(Path(__file__).resolve().parents[1] / 'installed/advanced-delegation-13b2c1c.json'),
                    '--admission-only'])
            except SystemExit as error:
                self.fail('Admission-only flag is missing or rejected: ' + str(error))
        return result, calls, steps, listener

    def test_admission_only_exits_after_inspection_before_any_product_access(self):
        result, calls, steps, listener = self.invoke(self.target())
        runner = importlib.import_module('s3_auto')
        self.assertEqual(calls, [('inspect', runner.TARGET), ('volume', 'inspect', runner.VOLUME)])
        self.assertEqual(steps, ['admission-before-any-mutation'])
        self.assertEqual(result, {'admission_only': True, 'container': 'synthetic-container', 'listeners': {'tcp': [], 'udp': []}})
        listener.assert_called_once_with()

    def test_admission_only_still_refuses_unsafe_target(self):
        runner = importlib.import_module('s3_auto')
        info = copy.deepcopy(self.target())
        info['HostConfig']['Privileged'] = True
        with self.assertRaisesRegex(runner.Failure, 'privilege policy differs'):
            self.invoke(info)

    def test_admission_only_still_refuses_exposed_listener(self):
        runner = importlib.import_module('s3_auto')
        with self.assertRaisesRegex(runner.Failure, 'synthetic exposed listener'):
            self.invoke(self.target(), runner.Failure('synthetic exposed listener'))
