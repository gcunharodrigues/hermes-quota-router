# Revisão S1 (decisions/log.md, 2026-11-19): command lock budgets must not leak into the hook worker, a busy `mode auto`
# must not leave a saved Auto behind, and register() must not wait for another process's cycle.
import fcntl
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock

from s2_fakes import claude, codex, reader_for
from test_f1f5_review import auto_manager
import test_s3_lifecycle as fixtures
from quota_router import lifecycle, storage


def hold_auto_lock(test, root, seconds):
    """Hold auto.lock through a separate open file description (as another process would) until released."""
    with storage.directory(root) as fd:
        handle = storage.open_record(fd, 'auto.lock', os.O_RDWR)
    fcntl.flock(handle, fcntl.LOCK_EX)
    release = threading.Event()

    def hold():
        release.wait(seconds)
        fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)
    holder = threading.Thread(target=hold)
    holder.start()
    test.addCleanup(holder.join)
    test.addCleanup(release.set)
    return release, holder


def events_recorded(root):
    path = Path(root) / 'events.json'
    return len(json.loads(path.read_text())) if path.exists() else 0


class WorkerBudgetTests(unittest.TestCase):
    """F1: a worker created by `mode auto` must not inherit the command's absolute lock deadline."""

    def test_worker_created_under_an_expired_command_deadline_records_every_event(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(lifecycle, 'COMMAND_LOCK_BUDGET_S', 0.3):
                m, ctx, _ = auto_manager(self, root)
            time.sleep(0.5)  # the command's deadline is now in the past
            for i in range(5):
                ctx.hooks['subagent_start'](session_id=f'p{i}', child_session_id=f'c{i}', parent_session_id='p')
            m.wait_hooks()
            self.assertEqual(events_recorded(root), 5)


class BusyTypeTests(unittest.TestCase):
    """F6: only the lock budget answers busy; a network timeout is a failure, not a running cycle."""

    def test_socket_timeout_in_a_command_is_not_reported_busy(self):
        import socket
        with tempfile.TemporaryDirectory() as root:
            m, _, _ = auto_manager(self, root)
            with mock.patch.object(m, 'sources', side_effect=socket.timeout('timed out')):
                payload = json.loads(m.command('status --json'))
            self.assertNotIn('busy', payload)
            self.assertFalse(payload['ok'])
            self.assertNotEqual(payload.get('error'), lifecycle.BUSY)

    def test_lock_budget_raises_the_dedicated_busy_type(self):
        from quota_router.apply import LockBusy
        with tempfile.TemporaryDirectory() as root:
            m, _, _ = auto_manager(self, root)
            hold_auto_lock(self, root, 5)
            token = lifecycle.LOCK_DEADLINE.set(time.monotonic() + 0.2)
            try:
                with self.assertRaises(LockBusy):
                    with m.engine.locked():
                        pass
            finally:
                lifecycle.LOCK_DEADLINE.reset(token)


class BusyModeAutoTests(unittest.TestCase):
    """F2: `mode auto` answered busy must leave the saved mode as it was, not a saved Auto that is not running."""

    def test_busy_mode_auto_keeps_the_saved_mode(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            helper = fixtures.AutoCommandTests()
            self.assertEqual(helper.call(m, 'mode observe')['mode_effective'], 'observe')
            release, holder = hold_auto_lock(self, root, 5)
            with mock.patch.object(lifecycle, 'COMMAND_LOCK_BUDGET_S', 0.3):
                payload = helper.call(m, 'mode auto')
            self.assertTrue(payload.get('busy'), payload)
            self.assertEqual((m.mode, ctx.settings['mode']), ('observe', 'observe'))
            self.assertIsNone(m.worker)
            release.set()
            holder.join()
            self.assertEqual(helper.call(m, 'mode auto')['mode_effective'], 'auto')
            self.assertEqual(ctx.settings['mode'], 'auto')


class ModeChangedBusyTests(unittest.TestCase):
    """F5: a mode change that succeeded is reported as changed even when the final status runs out of budget."""

    def change_then_hold(self, m, ctx, root, as_json):
        original = ctx.set_config

        def set_config(key, value):
            original(key, value)
            if key == 'mode':
                hold_auto_lock(self, root, 5)
        with mock.patch.object(ctx, 'set_config', set_config), \
                mock.patch.object(lifecycle, 'COMMAND_LOCK_BUDGET_S', 0.5):
            return m.command('mode observe' + (' --json' if as_json else ''))

    def test_json_reply_says_the_mode_changed_and_status_is_busy(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            payload = json.loads(self.change_then_hold(m, ctx, root, True))
            self.assertEqual((payload.get('mode_changed'), payload.get('busy')), ('observe', True), payload)
            self.assertEqual((m.mode, ctx.settings['mode']), ('observe', 'observe'))

    def test_text_reply_says_the_mode_changed_and_status_is_busy(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            text = self.change_then_hold(m, ctx, root, False)
            self.assertNotEqual(text, lifecycle.BUSY)
            self.assertIn('Modo alterado para observe', text)


class CycleTimingLockTests(unittest.TestCase):
    """F4: cycle_timings.json is a read-modify-write; it happens under auto.lock, through the Engine's atomic persist."""

    def test_cycle_timings_are_written_while_holding_auto_lock(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            m._last_hook_cycle = None
            writes = []
            original = storage.publish

            def publish(fd, name, value):
                if name == lifecycle.CYCLE_TIMINGS:
                    writes.append(m.engine._holder == threading.get_ident() and fd == m.engine._directory_fd)
                return original(fd, name, value)
            with mock.patch.object(storage, 'publish', publish):
                ctx.hooks['pre_llm_call'](session_id='s1')
                m.wait_hooks()
            self.assertEqual(writes, [True])
            self.assertEqual(json.loads((Path(root) / lifecycle.CYCLE_TIMINGS).read_text())[-1]['trigger'], 'pre_llm_call')


class RegisterLockBudgetTests(unittest.TestCase):
    """F3: Hermes abandons a plugin load after 10 s; register() must not wait for another process's 20-35 s cycle."""

    def test_register_returns_quickly_and_the_first_cycle_starts_auto(self):
        from s3_fakes import qualified
        from quota_router.events import HOOKS
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = auto_manager(self, root)
            m.close()
            self.assertEqual(ctx.settings['mode'], 'auto')
            ctx.hooks.clear()
            # The next process: another process's production cycle holds auto.lock while this one loads the plugin.
            release, holder = hold_auto_lock(self, root, 20)
            reader = reader_for(openai_codex=codex(10), anthropic=claude(100))
            started = time.monotonic()
            with self.assertLogs(lifecycle.LOG.name, 'WARNING') as logs:
                m2 = lifecycle.Management(ctx, importer=lambda: reader, sources=lambda: (backend.read(), []),
                                          clock=lambda: m.clock(), profile=lambda: 'default', backend=backend,
                                          data_dir=root, compatible=qualified)
            elapsed = time.monotonic() - started
            self.assertIn('Auto begins on the first cycle', logs.output[-1])
            self.addCleanup(m2.close)
            self.assertLess(elapsed, 4)
            self.assertEqual(m2.mode, 'auto')
            self.assertEqual(set(ctx.hooks), set(HOOKS))  # hooks can only be registered while the plugin loads
            self.assertEqual(backend.document['model']['provider'], 'anthropic')
            release.set()
            holder.join()
            ctx.hooks['pre_llm_call'](session_id='s1')
            m2.wait_hooks()
            self.assertEqual(backend.document['model']['provider'], 'openai-codex')
            state = json.loads((Path(root) / 'state.json').read_text())
            self.assertTrue(state['auto_declared'])
            status = json.loads(m2.command('status --json'))
            self.assertEqual((status['mode_effective'], status['mode_saved']), ('auto', 'auto'))
            self.assertNotIn('auto_suspended', status)

    def test_register_with_saved_observe_returns_quickly_and_loads_retained_state_later(self):
        from s3_fakes import qualified
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = auto_manager(self, root)
            m.close()
            ctx.settings['mode'] = 'observe'
            release, holder = hold_auto_lock(self, root, 20)
            started = time.monotonic()
            with self.assertLogs(lifecycle.LOG.name, 'WARNING'):
                m2 = lifecycle.Management(ctx, importer=m.importer, sources=lambda: (backend.read(), []),
                                          clock=lambda: m.clock(), profile=lambda: 'default', backend=backend,
                                          data_dir=root, compatible=qualified)
            self.addCleanup(m2.close)
            self.assertLess(time.monotonic() - started, 4)
            self.assertEqual(m2.mode, 'observe')
            release.set()
            holder.join()
            status = json.loads(m2.command('status --json'))
            self.assertEqual(status['mode_effective'], 'observe')
            self.assertTrue(status['applied']['auto_declared'])


if __name__ == '__main__':
    unittest.main()
