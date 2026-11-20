"""Correções de 2026-11-18 (decisions/log.md): each test failed before its fix."""
import json
import tempfile
import threading
import unittest

from s2_fakes import NOW, claude, codex
from s3_fakes import Backend, qualified
from test_f1f5_review import auto_manager
from test_s3_lifecycle import AutoContext
from quota_router.lifecycle import Management


def call(manager, command):
    return json.loads(manager.command(command + ' --json'))


class TransientSettingsReadTests(unittest.TestCase):
    def test_one_failed_settings_read_does_not_suspend_auto_until_restart(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = auto_manager(self, root)
            original, failures = ctx.get_config, [1]

            def flaky(key, default=None):
                if failures[0]:
                    failures[0] -= 1
                    raise OSError('transient native error')
                return original(key, default)

            ctx.get_config = flaky
            self.assertFalse(call(m, 'status')['ok'])
            again = call(m, 'status')
            self.assertTrue(again['ok'], again.get('auto_reason'))
            self.assertTrue(again['auto_available'], again.get('auto_reason'))
            self.assertNotIn('auto_suspended', again)
            # OFF still restores: the earlier failed read no longer blocks the Auto gate it needs.
            self.assertTrue(call(m, 'mode off')['ok'])


class EngineLockThreadTests(unittest.TestCase):
    """The hook worker records events under the Auto lock in its own thread while commands and cycles run elsewhere."""

    def test_status_waits_for_another_thread_holding_the_auto_lock(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = auto_manager(self, root)
            held, release = threading.Event(), threading.Event()

            def record():
                with m.engine.locked():
                    held.set()
                    release.wait(5)

            worker = threading.Thread(target=record)
            worker.start()
            self.assertTrue(held.wait(5))
            threading.Timer(0.2, release.set).start()
            during = call(m, 'status')
            worker.join(5)
            self.assertNotIn('error', during)
            self.assertTrue(during['auto_available'], during.get('auto_reason'))
            self.assertTrue(call(m, 'status')['auto_available'])

    def test_the_same_thread_still_cannot_take_the_lock_twice(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = auto_manager(self, root)
            with m.engine.locked():
                with self.assertRaises(RuntimeError):
                    with m.engine.locked():
                        pass


class RestartHysteresisTests(unittest.TestCase):
    """Pacing scores codex 70% -> 0.70, 62% -> 0.887, 50% -> 1.17 and Claude 40% -> 0.84 (week resets 72 h and 120 h)."""

    def test_restart_keeps_the_applied_provider_until_the_challenger_clears_the_hysteresis(self):
        with tempfile.TemporaryDirectory() as root:
            ctx, backend, used = AutoContext(), Backend(), {'codex': 70}

            def reader(provider):
                return codex(used['codex']) if provider == 'openai-codex' else claude(40)

            def build():
                manager = Management(ctx, importer=lambda: reader, sources=lambda: (backend.read(), []), clock=lambda: NOW,
                                     profile=lambda: 'default', backend=backend, data_dir=root, compatible=qualified)
                self.addCleanup(manager.close)
                return manager

            def general():
                options = backend.document['delegation']['backends']['model_map']['options']
                return next(option['provider'] for option in options if option['name'] == 'general')

            m = build()
            call(m, 'config approve-map base')
            self.assertEqual(call(m, 'mode auto')['mode_effective'], 'auto')
            call(m, 'apply')
            self.assertEqual(general(), 'anthropic')
            used['codex'] = 62
            m.cache.clear()
            call(m, 'apply')
            self.assertEqual(general(), 'anthropic')
            m.close()
            # The gateway restarts: the route this plugin applied is the preference the hysteresis protects.
            restarted = build()
            self.assertEqual(call(restarted, 'apply')['mode_effective'], 'auto')
            self.assertEqual(general(), 'anthropic')
            used['codex'] = 50
            restarted.cache.clear()
            call(restarted, 'apply')
            self.assertEqual(general(), 'openai-codex')


if __name__ == '__main__':
    unittest.main()
