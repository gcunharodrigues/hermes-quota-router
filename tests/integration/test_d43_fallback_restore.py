"""D-43: recovery by equality does not authorize restoration of a manual chain."""
import copy
import unittest

import test_hqr38_fallback as support


class InterruptedBeforeWrite(RuntimeError):
    pass


class FallbackRestoreTests(unittest.TestCase):
    def test_off_and_observe_preserve_manual_target_after_interruption(self):
        harness = support.SafetyNetLifecycleTests()
        chain = [support.OPUS]
        for mode in ('off', 'observe'):
            for manual in (False, True):
                with self.subTest(mode=mode, manual=manual), harness.fixture() as (manager, backend, _, _):
                    harness.call(manager, 'config approve-map base')
                    harness.call(manager, 'mode auto')
                    engine = manager.engine
                    assert engine is not None
                    selection = {'fallback:conversation': {'chain': chain}}
                    self.assertNotEqual(backend.read()['fallback_providers'], chain)
                    if manual:
                        def stop(point):
                            if point == 'journal':
                                raise InterruptedBeforeWrite()
                        engine.checkpoint = stop
                        with self.assertRaises(InterruptedBeforeWrite):
                            engine.cycle(selection, now=100, enabled={'conversation', 'general', 'fallback:conversation', 'fallback:general'})
                        engine.checkpoint = lambda _: None
                        self.assertNotEqual(backend.read()['fallback_providers'], chain)
                        backend.write({'fallback_providers': chain}, ())
                    else:
                        engine.cycle(selection, now=100, enabled={'conversation', 'general', 'fallback:conversation', 'fallback:general'})
                    self.assertEqual(backend.read()['fallback_providers'], chain)
                    harness.call(manager, 'mode ' + mode)
                    expected = copy.deepcopy(support.CONFIG)
                    if manual:
                        expected['fallback_providers'] = chain
                    self.assertEqual(backend.read(), expected)
