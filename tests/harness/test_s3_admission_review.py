"""Installed-runner admission rejects mutations using inert Docker responses."""
import copy
import importlib
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class AdmissionReviewTests(unittest.TestCase):
    def test_negative_isolation_controls_stop_before_any_install(self):
        runner = importlib.import_module('s3_auto')
        observe = importlib.import_module('s2_observe')
        valid = {'Id': 'synthetic-container', 'Image': 'synthetic-image',
                 'Config': {'User': '10001:10001', 'Labels': {'hqr.task': observe.TASK_LABEL}},
                 'HostConfig': {'CapDrop': ['ALL'], 'CapAdd': [], 'Privileged': False, 'NetworkMode': 'bridge',
                                'PortBindings': {}, 'PublishAllPorts': False, 'SecurityOpt': ['no-new-privileges=true'],
                                'PidMode': '', 'IpcMode': 'private', 'Binds': [observe.VOLUME + ':' + observe.STATE]},
                 'NetworkSettings': {'Networks': {'bridge': {}}},
                 'Mounts': [{'Type': 'volume', 'Name': observe.VOLUME, 'Destination': observe.STATE, 'Driver': 'local', 'RW': True}]}
        volume = {'Driver': 'local', 'Options': {}, 'Labels': {'hqr.task': observe.TASK_LABEL}}
        mutations = [lambda i, v: i['Config']['Labels'].clear(),
                     lambda i, v: i['Mounts'][0].update(Name='foreign'),
                     lambda i, v: v.update(Options={'device': '/foreign'}),
                     lambda i, v: i['HostConfig'].update(CapAdd=['SYS_ADMIN']),
                     lambda i, v: i['HostConfig'].update(SecurityOpt=[]),
                     lambda i, v: i['HostConfig'].update(PidMode='host'),
                     lambda i, v: i['HostConfig'].update(IpcMode='host'),
                     lambda i, v: i['HostConfig'].update(PublishAllPorts=True),
                     lambda i, v: i['NetworkSettings'].update(Networks={'foreign': {}})]
        import json
        for index, mutate in enumerate(mutations):
            with self.subTest(control=index):
                info, vol = copy.deepcopy(valid), copy.deepcopy(volume)
                mutate(info, vol)
                calls = []
                class Run:
                    def __init__(self, _path):
                        pass
                    def docker(self, *args):
                        return types.SimpleNamespace(stdout=json.dumps([vol if args[0] == 'volume' else info]))
                    def step(self, _name, fn):
                        return fn()
                    def probe(self, *_args):
                        calls.append('probe')
                        raise AssertionError('Reached product before admission')
                    def hermes(self, *_args):
                        calls.append('install')
                        raise AssertionError('Reached install before admission')
                with mock.patch.object(runner, 'S2Run', Run), \
                        mock.patch.object(runner, 'parse', return_value=types.SimpleNamespace(receipts='unused', candidate='a' * 40)), \
                        mock.patch.object(runner, 'listener_admission', return_value={}):
                    with self.assertRaises(runner.Failure):
                        runner.main(['--advanced-manifest', 'unused'])
                self.assertEqual(calls, [])
