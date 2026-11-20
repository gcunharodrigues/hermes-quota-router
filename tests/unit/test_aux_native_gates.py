# Contract: decisions/aux-plan.md, registry without discovery, D-AUXP-3 and qualification pending.
"""Auxiliary writes need the main host qualification; registry inspection never discovers plugins."""
import sys
from threading import RLock
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from quota_router import auxiliary, compat


class AuxiliaryNativeGateTests(unittest.TestCase):
    def test_auxiliary_native_qualification_follows_the_main_host_qualification(self):
        # decision D-36: no separate auxiliary fingerprint set.
        with patch.object(compat, '_source_compatibility', return_value={'ok': True, 'reasons': [], 'host': 'h'}):
            self.assertTrue(compat.native_auxiliary_compatibility()['ok'])
        with patch.object(compat, '_source_compatibility', return_value={'ok': False, 'reasons': ['host_not_qualified']}):
            result = compat.native_auxiliary_compatibility()
        self.assertFalse(result['ok'])
        self.assertTrue(result['fingerprint_failure'])
        self.assertEqual(result['reasons'], ['host_not_qualified'])

    def test_registry_reads_only_current_home_under_lock_and_never_discovers(self):
        lock = RLock()
        def forbidden(*args, **kwargs):
            self.fail('Registry lookup must never discover or create a manager')
        module = SimpleNamespace(_plugin_managers_lock=lock, _plugin_home_key=lambda: 'synthetic-home',
                                 _plugin_managers_by_home={'synthetic-home': SimpleNamespace(_aux_tasks={
                                     'child_task': {'inherit_from': 'compression'}, 'approval': {}})},
                                 get_plugin_manager=forbidden, get_plugin_auxiliary_tasks=forbidden,
                                 _ensure_plugins_discovered=forbidden)
        with patch.dict(sys.modules, {'hermes_cli.plugins': module}):
            result = auxiliary.native_registry()
            self.assertTrue(result['ok'])
            self.assertEqual(result['tasks'], {'child_task': {'inherit_from': 'compression'}, 'approval': {}})
            module._plugin_managers_by_home = {}
            self.assertFalse(auxiliary.native_registry()['ok'])
        with patch.dict(sys.modules, {'hermes_cli.plugins': None}):
            self.assertFalse(auxiliary.native_registry()['ok'])
