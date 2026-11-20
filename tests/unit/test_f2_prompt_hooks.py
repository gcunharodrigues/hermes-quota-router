# decision D-33: decide on each prompt, at session start and before each delegation.
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Event
import unittest

from quota_router import events
from quota_router.events import HOOKS, READER_CONTEXT, REFRESH, HookWorker

NOW = datetime(2026, 11, 18, 23, 0, tzinfo=timezone.utc)
scope = ContextVar('synthetic_secret_scope', default='no-scope')


class Recorder:
    def __init__(self):
        self.calls, self.done = [], Event()

    def __call__(self):
        caller = READER_CONTEXT.get()
        self.calls.append({'owner_scope': scope.get(), 'reader_scope': caller.run(scope.get) if caller else None,
                           'refresh': REFRESH.get()})
        self.done.set()


class TriggerTests(unittest.TestCase):
    def worker(self):
        cycle = Recorder()
        token = scope.set('owner')
        worker = HookWorker(None, cycle, lambda: NOW)
        scope.reset(token)
        self.addCleanup(worker.close)
        return worker, cycle

    def test_kanban_tick_is_no_longer_a_trigger(self):
        self.assertNotIn('on_kanban_dispatch_tick', HOOKS)
        for name in ('pre_llm_call', 'on_session_start', 'pre_tool_call'):
            self.assertIn(name, HOOKS)

    def test_prompt_cycle_reads_quota_in_the_callers_scope_and_keeps_the_owner_context(self):
        worker, cycle = self.worker()
        token = scope.set('caller-profile')
        try:
            self.assertIsNone(worker.callback('pre_llm_call')(user_message='secret prompt', session_id='s1'))
        finally:
            scope.reset(token)
        self.assertTrue(cycle.done.wait(2))
        worker.wait()
        self.assertEqual(cycle.calls, [{'owner_scope': 'owner', 'reader_scope': 'caller-profile', 'refresh': None}])

    def test_delegation_decides_synchronously_before_the_tool_runs(self):
        worker, cycle = self.worker()
        token = scope.set('caller-profile')
        try:
            worker.callback('pre_tool_call')(tool_name='delegate_task', args={})
        finally:
            scope.reset(token)
        self.assertEqual(cycle.calls, [{'owner_scope': 'owner', 'reader_scope': 'caller-profile', 'refresh': None}])

    def test_other_tools_do_not_cycle(self):
        worker, cycle = self.worker()
        worker.callback('pre_tool_call')(tool_name='terminal', args={'command': 'ls'})
        worker.wait()
        self.assertEqual(cycle.calls, [])

    def test_rate_limit_forces_a_fresh_reading_of_that_provider(self):
        worker, cycle = self.worker()
        worker.callback('api_request_error')(provider='anthropic', error={'type': 'RateLimitError', 'message': 'x'})
        self.assertTrue(cycle.done.wait(2))
        worker.wait()
        self.assertEqual(cycle.calls[0]['refresh'], ('anthropic',))

    def test_other_errors_do_not_cycle(self):
        worker, cycle = self.worker()
        worker.callback('api_request_error')(provider='anthropic', error={'type': 'APIError', 'message': 'x'})
        worker.wait()
        self.assertEqual(cycle.calls, [])


class ThrottleTests(unittest.TestCase):
    def manager(self):
        from quota_router.lifecycle import Management

        class Bare(Management):
            def __init__(self):
                from threading import RLock
                self.lock, self.mode, self.closed, self.cache = RLock(), 'auto', False, {'anthropic': {'state': 'ok'}}
                self._last_hook_cycle, self.now, self.runs = None, 0.0, 0
                self._forced, self.rate_limited = {}, {}
                self.clock = lambda: datetime.fromtimestamp(self.now, timezone.utc)

            def status(self, detail=False):
                self.runs += 1
                return {}
        return Bare()

    def test_bursts_coalesce_and_a_rate_limit_bypasses_the_interval(self):
        m = self.manager()
        m.hook_cycle()
        m.now = 5.0
        m.hook_cycle()
        self.assertEqual(m.runs, 1)
        events.run_cycle(m.hook_cycle, None, 'anthropic')
        self.assertEqual((m.runs, m.cache), (2, {}))
        # Revisão F1–F5, R3: a second rate limit inside the forced-refresh interval is just another throttled cycle.
        m.cache['anthropic'] = {'state': 'ok'}
        m.now = 6.0
        events.run_cycle(m.hook_cycle, None, 'anthropic')
        self.assertEqual((m.runs, m.cache), (2, {'anthropic': {'state': 'ok'}}))
        m.now = 5.0 + m.MIN_CYCLE_INTERVAL_S
        m.hook_cycle()
        self.assertEqual(m.runs, 3)


class CompatParseCacheTests(unittest.TestCase):
    def test_each_unchanged_file_is_parsed_once(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from quota_router import compat
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'mod.py'
            path.write_text('def a():\n    return 1\n\ndef b():\n    return 2\n', encoding='utf-8')
            with mock.patch.object(compat.ast, 'parse', wraps=compat.ast.parse) as parse:
                self.assertIn('return 1', compat.source_object(path, 'a'))
                self.assertIn('return 2', compat.source_object(path, 'b'))
                self.assertEqual(parse.call_count, 1)
                path.write_text('def a():\n    return 3\n', encoding='utf-8')
                self.assertIn('return 3', compat.source_object(path, 'a'))
                self.assertEqual(parse.call_count, 2)


if __name__ == '__main__':
    unittest.main()
