# Incidente 19/11 (decisions/log.md, 2026-11-19): Hermes gives pre_tool_call 30 s, fails it closed and then suspends
# the callback for 60 s; a sync plugin command is not time-bounded at all. No cycle runs in the caller's thread.
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
from test_f1f5_review import Gate, auto_manager
from quota_router import events, lifecycle, storage
from quota_router.apply import Engine
from quota_router.events import HookWorker
from s2_fakes import NOW


def slow_cycles(test, seconds):
    """Patch Engine.cycle_locked to wait up to `seconds` (or until released) before the real cycle."""
    entered, release = threading.Event(), threading.Event()
    original = Engine.cycle_locked

    def slow(engine, *args, **kwargs):
        entered.set()
        release.wait(seconds)
        return original(engine, *args, **kwargs)
    patcher = mock.patch.object(Engine, 'cycle_locked', slow)
    patcher.start()
    test.addCleanup(patcher.stop)
    test.addCleanup(release.set)
    return entered, release


def timed(call, *args, **kwargs):
    started = time.monotonic()
    result = call(*args, **kwargs)
    return result, time.monotonic() - started


class DelegationBudgetTests(unittest.TestCase):
    def test_delegate_hook_returns_within_budget_when_the_cycle_is_slow(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            m._last_hook_cycle = None  # cached quota from `mode auto`; the slow part is the write cycle
            entered, release = slow_cycles(self, 40)
            result, elapsed = timed(ctx.hooks['pre_tool_call'], tool_name='delegate_task', args={})
            self.assertIsNone(result)
            self.assertLess(elapsed, events.DELEGATION_BUDGET_S + 1)
            self.assertTrue(entered.is_set())
            # Another tool is never held by the running cycle.
            result, elapsed = timed(ctx.hooks['pre_tool_call'], tool_name='terminal', args={'command': 'ls'})
            self.assertIsNone(result)
            self.assertLess(elapsed, 0.5)
            release.set()
            m.wait_hooks()
            self.assertIsNotNone(m._last_hook_cycle)
            state = json.loads((Path(root) / 'state.json').read_text())
            self.assertEqual(state['last_cycle'], NOW.timestamp())

    def test_fast_cycle_is_applied_before_the_delegate_hook_returns(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = auto_manager(self, root)
            self.assertEqual(backend.document['model']['provider'], 'anthropic')
            # The quota changed and the cache is stale: the worker fetches and applies within the budget.
            reader = reader_for(openai_codex=codex(10), anthropic=claude(100))
            m.importer, m._last_hook_cycle = (lambda: reader), None
            m.cache.clear()
            result, elapsed = timed(ctx.hooks['pre_tool_call'], tool_name='delegate_task', args={})
            self.assertIsNone(result)
            self.assertLess(elapsed, events.DELEGATION_BUDGET_S)
            self.assertEqual(backend.document['model']['provider'], 'openai-codex')

    def test_the_cycle_never_runs_in_the_hook_thread(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            threads = []
            original = m.status
            m.status = lambda *args, **kwargs: (threads.append(threading.current_thread().name), original(*args, **kwargs))[1]
            m._last_hook_cycle = None
            ctx.hooks['pre_tool_call'](tool_name='delegate_task', args={})
            m.wait_hooks()
            self.assertEqual(threads, ['quota-router-hooks'])


class Blocking:
    def __init__(self):
        self.calls, self.entered, self.release = 0, threading.Event(), threading.Event()

    def __call__(self):
        self.calls += 1
        self.entered.set()
        self.release.wait(10)


class WorkerCoalescingTests(unittest.TestCase):
    def worker(self, cycle):
        worker = HookWorker(None, cycle, lambda: NOW)
        self.addCleanup(worker.close)
        self.addCleanup(cycle.release.set)
        return worker

    def test_delegation_waits_for_the_running_cycle_instead_of_queuing_another(self):
        cycle = Blocking()
        worker = self.worker(cycle)
        worker.callback('pre_llm_call')(session_id='s1')
        self.assertTrue(cycle.entered.wait(2))
        with mock.patch.object(events, 'DELEGATION_BUDGET_S', 0.2):
            _, elapsed = timed(worker.callback('pre_tool_call'), tool_name='delegate_task', args={})
        self.assertLess(elapsed, 1)
        cycle.release.set()
        worker.wait()
        self.assertEqual(cycle.calls, 1)

    def test_delegation_joins_the_queued_cycle(self):
        cycle = Blocking()
        worker = self.worker(cycle)
        worker.callback('pre_llm_call')(session_id='s1')
        self.assertTrue(cycle.entered.wait(2))
        worker.callback('on_session_start')(session_id='s2')  # queued behind the running one
        with mock.patch.object(events, 'DELEGATION_BUDGET_S', 0.2):
            worker.callback('pre_tool_call')(tool_name='delegate_task', args={})
        cycle.release.set()
        worker.wait()
        self.assertEqual(cycle.calls, 2)

    def test_delegation_returns_once_the_cycle_completes(self):
        cycle = Blocking()
        cycle.release.set()
        worker = self.worker(cycle)
        _, elapsed = timed(worker.callback('pre_tool_call'), tool_name='delegate_task', args={})
        self.assertEqual(cycle.calls, 1)
        self.assertLess(elapsed, 1)

    def test_any_failure_returns_none(self):
        def broken():
            raise RuntimeError('secret-token')
        worker = HookWorker(None, broken, lambda: NOW)
        self.addCleanup(worker.close)
        self.assertIsNone(worker.callback('pre_tool_call')(tool_name='delegate_task', args={}))
        with mock.patch.object(worker, 'enqueue', side_effect=RuntimeError('boom')):
            self.assertIsNone(worker.callback('pre_tool_call')(tool_name='delegate_task', args={}))


class CommandBudgetTests(unittest.TestCase):
    def call(self, m, command):
        return json.loads(m.command(command + ' --json'))

    def hold_manager_lock(self, m, seconds):
        held, release = threading.Event(), threading.Event()

        def hold():
            with m.lock:
                held.set()
                release.wait(seconds)
        holder = threading.Thread(target=hold)
        holder.start()
        self.addCleanup(holder.join)
        self.addCleanup(release.set)
        self.assertTrue(held.wait(2))
        return release

    def hold_auto_lock(self, root, seconds):
        with storage.directory(root) as fd:
            handle = storage.open_record(fd, 'auto.lock', os.O_RDWR)
        fcntl.flock(handle, fcntl.LOCK_EX)
        timer = threading.Timer(seconds, lambda: (fcntl.flock(handle, fcntl.LOCK_UN), os.close(handle)))
        timer.start()
        self.addCleanup(timer.join)
        return timer

    def test_command_replies_busy_while_a_cycle_holds_the_manager_lock(self):
        with tempfile.TemporaryDirectory() as root:
            m, _, _ = auto_manager(self, root)
            release = self.hold_manager_lock(m, 6)
            with mock.patch.object(lifecycle, 'COMMAND_LOCK_BUDGET_S', 0.3):
                text, elapsed = timed(m.command, 'status')
                payload = self.call(m, 'status')
            self.assertLess(elapsed, 2)
            self.assertIn('tente novamente', text)
            self.assertEqual((payload['ok'], payload['busy']), (False, True))
            release.set()
            self.assertIsNone(m.auto_failure)
            self.assertEqual(self.call(m, 'status')['mode_effective'], 'auto')

    def test_apply_and_mode_reply_busy_while_another_process_holds_auto_lock(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = auto_manager(self, root)
            writes = len(backend.writes)
            timer = self.hold_auto_lock(root, 6)
            with mock.patch.object(lifecycle, 'COMMAND_LOCK_BUDGET_S', 0.3):
                for command in ('apply', 'mode off'):
                    with self.subTest(command=command):
                        payload, elapsed = timed(self.call, m, command)
                        self.assertLess(elapsed, 2)
                        self.assertEqual((payload['ok'], payload['busy']), (False, True))
            self.assertEqual(len(backend.writes), writes)
            self.assertIsNone(m.auto_failure)
            self.assertEqual(m.mode, 'auto')
            self.assertEqual(ctx.settings['mode'], 'auto')
            timer.join()
            self.assertTrue(self.call(m, 'apply')['ok'])

    def test_status_answers_from_last_known_readings_and_refreshes_in_background(self):
        with tempfile.TemporaryDirectory() as root:
            m, _, _ = auto_manager(self, root)
            gate = Gate(self)
            m.importer = lambda: gate
            m.cache.clear()
            with mock.patch.object(lifecycle, 'COMMAND_FETCH_WAIT_S', 0.2), \
                    mock.patch.object(m, 'apply_decisions', wraps=m.apply_decisions) as applied:
                payload, elapsed = timed(self.call, m, 'status')
            self.assertLess(elapsed, 2)
            self.assertTrue(gate.entered.wait(2))
            self.assertNotIn('MainThread', gate.threads)
            self.assertEqual(payload['quota']['refresh'], 'pending')
            for provider, reading in payload['quota']['providers'].items():
                self.assertTrue(reading.get('last_known'), (provider, reading))
            applied.assert_not_called()  # no route write from a view that skipped the fetch
            with mock.patch.object(lifecycle, 'COMMAND_FETCH_WAIT_S', 0.2):
                text = m.command('status')
            self.assertIn('segundo plano', text)
            self.assertIn('O Auto não aplicou nada', text)
            gate.release.set()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not all(p in m.cache for p in ('openai-codex', 'anthropic')):
                time.sleep(0.05)
            self.assertEqual({r['state'] for r in m.cache.values()}, {'ok'})
            self.assertNotIn('refresh', self.call(m, 'status')['quota'])

    def test_apply_still_fetches(self):
        with tempfile.TemporaryDirectory() as root:
            m, _, backend = auto_manager(self, root)
            reader = reader_for(openai_codex=codex(10), anthropic=claude(100))
            m.importer = lambda: reader
            m.cache.clear()
            with mock.patch.object(lifecycle, 'COMMAND_FETCH_WAIT_S', 0):
                payload = self.call(m, 'apply')
            self.assertNotIn('refresh', payload['quota'])
            self.assertEqual(backend.document['model']['provider'], 'openai-codex')


class CycleTimingTests(unittest.TestCase):
    def test_slow_cycle_is_logged_and_its_phases_recorded(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            m._last_hook_cycle = None
            _, release = slow_cycles(self, 0.3)
            with mock.patch.object(lifecycle, 'SLOW_CYCLE_WARNING_S', 0.2), \
                    self.assertLogs(lifecycle.LOG.name, 'WARNING') as logs:
                ctx.hooks['pre_tool_call'](tool_name='delegate_task', args={})
                m.wait_hooks()
            self.assertEqual(len(logs.records), 1)
            self.assertIn('pre_tool_call', logs.output[0])
            records = json.loads((Path(root) / lifecycle.CYCLE_TIMINGS).read_text())
            last = records[-1]
            self.assertEqual(set(last), {'at', 'trigger', 'seconds'})
            self.assertEqual(last['trigger'], 'pre_tool_call')
            self.assertEqual(set(last['seconds']), {'readings', 'main', 'auxiliary', 'total'})
            self.assertGreaterEqual(last['seconds']['main'], 0.3)
            self.assertIsNone(last['seconds']['auxiliary'])
            self.assertGreaterEqual(last['seconds']['total'], last['seconds']['main'])

    def test_fast_cycle_is_recorded_without_a_warning(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            m._last_hook_cycle = None
            with self.assertNoLogs(lifecycle.LOG.name, 'WARNING'):
                ctx.hooks['pre_llm_call'](session_id='s1')
                m.wait_hooks()
            records = json.loads((Path(root) / lifecycle.CYCLE_TIMINGS).read_text())
            self.assertEqual(records[-1]['trigger'], 'pre_llm_call')


if __name__ == '__main__':
    unittest.main()
