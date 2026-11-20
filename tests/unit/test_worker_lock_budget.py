"""Bound contention without losing the next cycle or borrowing a waiter thread."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

from quota_router import apply, events
from test_f1f5_review import auto_manager


class WorkerLockBudgetTests(unittest.TestCase):
    @contextmanager
    def hold_lock(self, root):
        with subprocess.Popen(
            [sys.executable, '-c',
             'import fcntl, sys\n'
             'with open(sys.argv[1], "rb") as handle:\n'
             '    fcntl.flock(handle, fcntl.LOCK_EX)\n'
             '    print("locked", flush=True)\n'
             '    sys.stdin.read()\n', str(Path(root) / 'auto.lock')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        ) as child:
            assert child.stdin is not None and child.stdout is not None
            try:
                self.assertTrue(select.select([child.stdout], [], [], 5)[0], 'lock handshake timed out')
                self.assertEqual(child.stdout.readline().strip(), 'locked')
                yield child
            finally:
                child.stdin.close()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()

    def assert_drained(self, worker):
        queue = worker.queue
        with queue.all_tasks_done:
            self.assertTrue(queue.all_tasks_done.wait_for(lambda: not queue.unfinished_tasks, timeout=3),
                            'worker still waiting for the other process')

    def assert_no_new_waiter(self, before):
        self.assertFalse([t for t in threading.enumerate() if t not in before and t.name == 'quota-router-lock'])

    def test_cycle_defers_and_next_hook_recovers_without_restart(self):
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, _ = auto_manager(self, root)
            worker = manager.worker
            assert worker is not None
            timings = Path(root) / 'cycle_timings.json'
            before = json.loads(timings.read_text())
            waiters = set(threading.enumerate())
            with mock.patch.object(events, 'WORKER_LOCK_BUDGET_S', 0.1, create=True):
                with self.hold_lock(root) as child:
                    ctx.hooks['pre_llm_call']()
                    self.assert_drained(worker)
                    self.assertIsNone(child.poll())
                    self.assertEqual(json.loads(timings.read_text()), before)
                    self.assert_no_new_waiter(waiters)
                ctx.hooks['pre_llm_call']()
                self.assert_drained(worker)
            after = json.loads(timings.read_text())
            self.assertIs(manager.worker, worker)
            self.assertEqual(after[:-1], before)
            self.assertEqual(after[-1]['trigger'], 'pre_llm_call')

    def test_record_only_hook_does_not_pin_worker(self):
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, _ = auto_manager(self, root)
            worker = manager.worker
            assert worker is not None
            records = Path(root) / 'events.json'
            waiters = set(threading.enumerate())
            with mock.patch.object(events, 'WORKER_LOCK_BUDGET_S', 0.1, create=True):
                with self.hold_lock(root) as child:
                    ctx.hooks['subagent_start'](child_session_id='blocked')
                    self.assert_drained(worker)
                    self.assertIsNone(child.poll())
                    self.assertFalse(records.exists())
                    self.assert_no_new_waiter(waiters)
                ctx.hooks['subagent_start'](child_session_id='next')
                self.assert_drained(worker)
            salt = json.loads((Path(root) / 'salt.json').read_text())
            expected = hashlib.sha256((salt + 'next').encode()).hexdigest()
            self.assertEqual([r['child_session_id_hash'] for r in json.loads(records.read_text())], [expected])

    def test_deferred_auto_retries_initialization_after_second_lock_is_busy(self):
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, _ = auto_manager(self, root)
            worker = manager.worker
            assert worker is not None
            manager.auto_pending = manager.seed_pending = True
            original_load = manager.loaded_engines
            attempts = iter((True, False))

            def load_engines():
                if next(attempts):
                    raise apply.LockBusy('busy')
                original_load()

            with mock.patch.object(manager, 'loaded_engines', side_effect=load_engines) as load:
                ctx.hooks['pre_llm_call']()
                self.assert_drained(worker)
                self.assertTrue(manager.auto_pending)
                ctx.hooks['pre_llm_call']()
                self.assert_drained(worker)
                self.assertEqual(load.call_count, 2)
            self.assertFalse(manager.auto_pending)
            self.assertFalse(manager.seed_pending)

    def test_worker_does_not_retry_after_sleep_crosses_deadline(self):
        clock = SimpleNamespace(now=0.0)
        def sleep(delay):
            clock.now += delay + 1
        fake_time = SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep)
        deadline = apply.LOCK_DEADLINE.set(0.1)
        worker = apply.WORKER_TRY_LOCK.set(True)
        try:
            with mock.patch.object(apply, 'time', fake_time), \
                    mock.patch.object(apply.fcntl, 'flock', side_effect=[BlockingIOError(), None]) as flock:
                with self.assertRaises(apply.LockBusy):
                    apply._flock(3)
                flock.assert_called_once_with(3, apply.fcntl.LOCK_EX | apply.fcntl.LOCK_NB)
        finally:
            apply.WORKER_TRY_LOCK.reset(worker)
            apply.LOCK_DEADLINE.reset(deadline)
