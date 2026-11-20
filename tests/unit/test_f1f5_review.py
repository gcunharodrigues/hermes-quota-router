# Revisão F1–F5 (decisions/log.md, 2026-11-18): R1 to R8 and R10 of the independent review of the F1–F5 slices.
from contextlib import contextmanager
import copy
from datetime import timedelta
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

from s2_fakes import NOW, claude, codex, reader_for
import s3_fakes
import test_s3_lifecycle as fixtures
from test_f1_last_known import good
from test_f5_profile_home import load_entry
from quota_router import compat, events, readings, storage
from quota_router.events import HookWorker
from quota_router.lifecycle import Management
from quota_router.settings import DEFAULTS


def auto_manager(test, root):
    helper = fixtures.AutoCommandTests()
    m, ctx, backend = helper.manager(root)
    test.addCleanup(m.close)
    helper.call(m, 'config approve-map base')
    test.assertEqual(helper.call(m, 'mode auto')['mode_effective'], 'auto')
    return m, ctx, backend


class Gate:
    """A quota reader that blocks until released, recording the thread that called it."""
    def __init__(self, test):
        self.entered, self.release, self.threads = threading.Event(), threading.Event(), []
        self.inner = reader_for(openai_codex=codex(100), anthropic=claude(10))
        test.addCleanup(self.release.set)

    def __call__(self, provider):
        self.threads.append(threading.current_thread().name)
        self.entered.set()
        self.release.wait(10)
        return self.inner(provider)


class SynchronousDelegationTests(unittest.TestCase):
    """R1: pre_tool_call(delegate_task) never fetches quota nor waits unbounded; Hermes fails closed at 30 s.

    Incidente 19/11 (fix A): the bound is the delegation budget for the worker's cycle, no longer 2 s per lock.
    """

    def delegate(self, ctx):
        started = time.monotonic()
        self.assertIsNone(ctx.hooks['pre_tool_call'](tool_name='delegate_task', args={}))
        return time.monotonic() - started

    def test_slow_reader_defers_the_cycle_to_the_worker(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            gate = Gate(self)
            m.importer, m._last_hook_cycle = (lambda: gate), None
            m.cache.clear()
            self.assertLess(self.delegate(ctx), events.DELEGATION_BUDGET_S + 1)
            self.assertTrue(gate.entered.wait(3))
            self.assertEqual(set(gate.threads), {'quota-router-hooks'})
            gate.release.set()
            m.wait_hooks()

    def test_busy_manager_lock_returns_within_the_bound(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            m._last_hook_cycle = None
            held, release = threading.Event(), threading.Event()
            def hold():
                with m.lock:
                    held.set()
                    release.wait(10)
            holder = threading.Thread(target=hold)
            holder.start()
            self.addCleanup(holder.join)
            self.addCleanup(release.set)
            self.assertTrue(held.wait(2))
            self.assertLess(self.delegate(ctx), events.DELEGATION_BUDGET_S + 1)
            release.set()
            m.wait_hooks()

    def test_busy_auto_lock_returns_within_the_bound_without_writes(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, backend = auto_manager(self, root)
            m._last_hook_cycle = None
            writes = len(backend.writes)
            with storage.directory(root) as fd:
                handle = storage.open_record(fd, 'auto.lock', os.O_RDWR)
            try:
                fcntl.flock(handle, fcntl.LOCK_EX)
                self.assertLess(self.delegate(ctx), events.DELEGATION_BUDGET_S + 1)
                self.assertEqual(len(backend.writes), writes)
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
                os.close(handle)
            m.wait_hooks()

    def test_cached_readings_decide_synchronously(self):
        with tempfile.TemporaryDirectory() as root:
            m, ctx, _ = auto_manager(self, root)
            m._last_hook_cycle = None
            gate = Gate(self)
            m.importer = lambda: gate
            self.assertLess(self.delegate(ctx), 3)
            self.assertEqual(gate.threads, [])
            self.assertIsNotNone(m._last_hook_cycle)


class Recorder:
    def __init__(self, block=False):
        self.calls, self.entered, self.release = [], threading.Event(), threading.Event()
        if not block:
            self.release.set()

    def __call__(self):
        from quota_router.events import REFRESH
        self.calls.append(REFRESH.get())
        self.entered.set()
        self.release.wait(5)


class RateLimitTests(unittest.TestCase):
    """R3: detection by Hermes' reason/status, coalesced queue, bounded forced refresh that respects backoff."""

    def worker(self, cycle):
        worker = HookWorker(None, cycle, lambda: NOW)
        self.addCleanup(worker.close)
        return worker

    def test_reason_and_status_code_signal_a_rate_limit(self):
        for kwargs in ({'reason': 'rate_limit'}, {'reason': 'billing'}, {'status_code': 429},
                       {'error': {'type': 'RateLimitError'}}):
            with self.subTest(kwargs=kwargs):
                cycle = Recorder()
                worker = self.worker(cycle)
                worker.callback('api_request_error')(provider='anthropic', **dict({'error': {'type': 'APIError'}}, **kwargs))
                worker.wait()
                self.assertEqual(cycle.calls, [('anthropic',)])

    def test_other_errors_do_not_cycle(self):
        cycle = Recorder()
        worker = self.worker(cycle)
        worker.callback('api_request_error')(provider='anthropic', reason='server_error', status_code=500,
                                             error={'type': 'APIError'})
        worker.wait()
        self.assertEqual(cycle.calls, [])

    def test_retries_coalesce_into_one_pending_cycle(self):
        cycle = Recorder(block=True)
        worker = self.worker(cycle)
        worker.callback('pre_llm_call')()
        self.assertTrue(cycle.entered.wait(2))
        for _ in range(50):
            for provider in ('anthropic', 'openai-codex'):
                worker.callback('api_request_error')(provider=provider, status_code=429, error={'type': 'APIError'})
        self.assertEqual(sum('context' in item for item in list(worker.queue.queue)), 1)
        cycle.release.set()
        worker.wait()
        self.assertEqual(cycle.calls, [None, ('anthropic', 'openai-codex')])

    def test_forced_refresh_is_bounded_and_respects_backoff(self):
        m = Management.__new__(Management)
        m.cache, m._forced, m.rate_limited = {}, {}, {}
        m.clock = lambda: NOW
        now = NOW.timestamp()
        m.cache['anthropic'] = {'state': 'ok'}
        self.assertTrue(m.force_refresh(('anthropic',), now))
        m.cache['anthropic'] = {'state': 'ok'}
        self.assertFalse(m.force_refresh(('anthropic',), now + 29))
        self.assertIn('anthropic', m.cache)
        backing_off = {'state': 'unknown', 'retry_at': (NOW + timedelta(seconds=200)).isoformat()}
        m.cache['anthropic'] = backing_off
        self.assertFalse(m.force_refresh(('anthropic',), now + 31))
        self.assertIs(m.cache['anthropic'], backing_off)
        self.assertEqual(set(m.rate_limited), {'anthropic'})


def failing(provider):
    raise RuntimeError('usage endpoint down')


class LastKnownTests(unittest.TestCase):
    """R5/R6/R7/R8: carry-forward limits, failure diagnosis and the retained last readings."""

    def manager(self, root, reader):
        directory = Path(root) / 'data'
        m = Management(fixtures.AutoContext(), importer=lambda: reader, sources=lambda: ({}, []), clock=lambda: NOW,
                       profile=lambda: 'default', backend=s3_fakes.Backend(), data_dir=directory, compatible=s3_fakes.qualified)
        m.ensure_retained_engine()
        with storage.directory(directory, create=True):
            pass
        return m, directory

    def settings(self):
        return dict(DEFAULTS)

    def test_carry_forward_is_limited_to_five_hours(self):
        self.assertEqual(readings.LAST_KNOWN_MAX_AGE_S, 5 * 3600)
        last = {'anthropic': good(NOW - timedelta(hours=5, seconds=1), NOW + timedelta(hours=2), NOW + timedelta(days=5))}
        found, _ = readings.collect(['anthropic'], NOW, 300, reader=failing, cache={}, last_good=last)
        self.assertEqual(found['anthropic']['state'], 'unknown')

    def test_rate_limited_provider_is_not_decided_on_its_last_known_reading(self):
        last = {'anthropic': good(NOW - timedelta(minutes=5), NOW + timedelta(hours=2), NOW + timedelta(days=5))}
        found, _ = readings.collect(['anthropic'], NOW, 300, reader=failing, cache={}, last_good=last,
                                    no_carry={'anthropic'})
        self.assertEqual(found['anthropic']['state'], 'unknown')
        with tempfile.TemporaryDirectory() as root:
            m, _ = self.manager(root, failing)
            m.last_good().update(last)
            m.rate_limited['anthropic'] = NOW.timestamp()
            self.assertEqual(m.readings(self.settings())['anthropic']['state'], 'unknown')
            m.rate_limited.clear()
            m.cache.clear()
            self.assertTrue(m.readings(self.settings())['anthropic']['last_known'])

    def test_invalid_stored_reading_is_discarded_and_never_raises(self):
        bad = good(NOW - timedelta(minutes=5), NOW + timedelta(hours=2), NOW + timedelta(days=5))
        bad['windows'][0]['reset_at'] = 'not-a-date'
        self.assertFalse(readings.last_known_valid('anthropic', bad))
        self.assertIsNone(readings.carry_forward(bad, NOW))
        found, _ = readings.collect(['anthropic'], NOW, 300, reader=failing, cache={}, last_good={'anthropic': bad})
        self.assertEqual(found['anthropic']['state'], 'unknown')

    def test_last_good_loads_when_the_engine_appears(self):
        with tempfile.TemporaryDirectory() as root:
            stored = good(NOW - timedelta(minutes=5), NOW + timedelta(hours=2), NOW + timedelta(days=5))
            invalid = dict(stored, provider='anthropic', windows='bad')
            directory = Path(root) / 'data'
            with storage.directory(directory, create=True) as fd:
                storage.publish(fd, Management.LAST_GOOD, {'anthropic': stored, 'openai-codex': invalid})
            m = Management(fixtures.AutoContext(), importer=lambda: failing, sources=lambda: ({}, []), clock=lambda: NOW,
                           profile=lambda: 'default', backend=s3_fakes.Backend(), data_dir=directory,
                           compatible=s3_fakes.qualified)
            m.engine = None
            self.assertEqual(m.last_good(), {})
            m.ensure_retained_engine()
            self.assertEqual(m.last_good(), {'anthropic': stored})

    def test_fresh_readings_are_retained_and_unchanged_ones_not_rewritten(self):
        with tempfile.TemporaryDirectory() as root:
            m, directory = self.manager(root, reader_for(openai_codex=codex(10), anthropic=claude(10)))
            m.readings(self.settings())
            # R8: save_last_good must write last_readings.json.
            saved = json.loads((directory / Management.LAST_GOOD).read_text())
            self.assertEqual(set(saved), {'anthropic', 'openai-codex'})
            self.assertEqual(json.loads((directory / Management.LAST_FAILURES).read_text()) if
                             (directory / Management.LAST_FAILURES).exists() else {}, {})
            with mock.patch.object(storage, 'publish', wraps=storage.publish) as publish:
                m.readings(self.settings())
                self.assertEqual(publish.call_count, 0)

    def test_failures_record_follows_the_failure_set_and_its_time(self):
        with tempfile.TemporaryDirectory() as root:
            state: dict = {'reader': failing}
            m, directory = self.manager(root, lambda provider: state['reader'](provider))
            last = good(NOW - timedelta(minutes=5), NOW + timedelta(hours=2), NOW + timedelta(days=5))
            m.last_good()['anthropic'] = copy.deepcopy(last)
            found = m.readings(self.settings())
            failures = json.loads((directory / Management.LAST_FAILURES).read_text())
            self.assertEqual(failures['anthropic'], {'reason': 'reader_error', 'at': found['anthropic']['failed_at'],
                                                     'kept_last_known': True})
            self.assertEqual(failures['anthropic']['at'], NOW.isoformat())
            # R8: a carried-forward reading is not recorded as a fresh one.
            self.assertEqual(json.loads((directory / Management.LAST_GOOD).read_text())['anthropic']['fetched_at'],
                             last['fetched_at'])
            self.assertEqual(m.last_good()['anthropic'], last)
            self.assertNotIn('last_known', json.loads((directory / Management.LAST_GOOD).read_text())['anthropic'])
            state['reader'] = reader_for(openai_codex=codex(10), anthropic=claude(10))
            m.cache.clear()
            m.readings(self.settings())
            self.assertEqual(json.loads((directory / Management.LAST_FAILURES).read_text()), {})


class Context(fixtures.AutoContext):
    def on_unload(self, callback):
        self.unload = callback

    def register_command(self, name, handler, **kwargs):
        self.command = handler


class RegisterHomeTests(unittest.TestCase):
    """R4: the home bound around register() is authoritative; the install path only cross-checks it."""

    @contextmanager
    def hermes(self, home):
        module = types.ModuleType('hermes_constants')
        setattr(module, 'get_hermes_home', lambda: home)
        with mock.patch.dict(sys.modules, {'hermes_constants': module}):
            yield

    def register(self, home, install, settings=None):
        entry = load_entry()
        slot = install / 'plugins' / 'hermes-quota-router'
        slot.mkdir(parents=True, exist_ok=True)
        entry.__file__ = str(slot / '__init__.py')
        ctx = Context(settings)
        with self.hermes(home):
            entry.register(ctx)
        manager = ctx.unload.__self__
        self.addCleanup(manager.close)
        return manager, ctx

    def homes(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        homes = [root / 'profiles' / name for name in ('alpha', 'beta')]
        for home in homes:
            # Hermes homes are private; storage refuses group-writable ancestors.
            home.mkdir(mode=0o700, parents=True)
            home.chmod(0o700)
            home.parent.chmod(0o700)
            (home / 'config.yaml').write_text('model: {}\n')
        return homes

    def test_normal_install_pins_every_source_to_the_registering_home(self):
        alpha, _ = self.homes()
        manager, _ = self.register(alpha, alpha)
        self.assertIsNone(manager.auto_failure)
        self.assertEqual(manager.backend.path, alpha / 'config.yaml')
        self.assertEqual(Path(manager.data_dir), alpha / 'plugin-data' / 'hermes-quota-router')
        with mock.patch('hqr_f5_entry.native_sources', return_value=({}, [])) as pinned:
            manager.sources()
            pinned.assert_called_once_with(alpha / 'config.yaml')

    def test_symlinked_slot_keeps_the_registering_home(self):
        alpha, beta = self.homes()
        (beta / 'plugins' / 'hermes-quota-router').mkdir(parents=True)
        (alpha / 'plugins').mkdir()
        os.symlink(beta / 'plugins' / 'hermes-quota-router', alpha / 'plugins' / 'hermes-quota-router')
        manager, _ = self.register(alpha, alpha)
        self.assertIsNone(manager.auto_failure)
        self.assertEqual(manager.backend.path, alpha / 'config.yaml')

    def test_mismatch_refuses_auto(self):
        alpha, beta = self.homes()
        from quota_router.mapping import approved_base
        manager, ctx = self.register(beta, alpha, {'mode': 'auto', 'roles': approved_base()})
        self.assertEqual(manager.mode, 'unavailable')
        self.assertEqual(manager.auto_check(), {'ok': False, 'reasons': ['plugin_home_mismatch']})
        result = json.loads(ctx.command('mode auto --json'))
        self.assertFalse(result['ok'])
        self.assertIn('plugin_home_mismatch', result['error'])
        self.assertEqual(manager.backend.path, beta / 'config.yaml')
        self.assertFalse((alpha / 'plugin-data').exists())

    def test_missing_config_still_pins_the_profile(self):
        alpha, _ = self.homes()
        (alpha / 'config.yaml').unlink()
        manager, ctx = self.register(alpha, alpha)
        self.assertEqual(manager.backend.path, alpha / 'config.yaml')
        self.assertTrue(json.loads(ctx.command('status --json'))['mode_effective'] in ('off', 'unavailable'))
        self.assertFalse((alpha / 'config.yaml').exists())


class CompatCacheTests(unittest.TestCase):
    """R2/R10: digests are reused only while files and objects are unchanged; one parse entry per path."""

    def test_source_digest_follows_the_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'mod.py'
            path.write_text('def a():\n    return 1\n', encoding='utf-8')
            first = compat._source_digest('t.a', path, 'a', Path(root))
            with mock.patch.object(compat, 'source_object', wraps=compat.source_object) as inspected:
                self.assertEqual(compat._source_digest('t.a', path, 'a', Path(root)), first)
                self.assertEqual(inspected.call_count, 0)
                path.write_text('def a():\n    return 22\n', encoding='utf-8')
                self.assertNotEqual(compat._source_digest('t.a', path, 'a', Path(root)), first)
                self.assertEqual(inspected.call_count, 1)

    def test_loaded_digest_follows_the_object(self):
        def one():
            return 1

        def two():
            return 2
        first = compat._loaded_digest('t.f', one)
        self.assertEqual(compat._loaded_digest('t.f', one), first)
        self.assertNotEqual(compat._loaded_digest('t.f', two), first)

    def test_parse_cache_keeps_one_entry_per_path(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'mod.py'
            for value in range(3):
                path.write_text(f'def a():\n    return {value}\n' + ' ' * value, encoding='utf-8')
                compat._parsed(path)
            self.assertEqual([key for key in compat._PARSED if key.startswith(root)], [str(path)])


if __name__ == '__main__':
    unittest.main()
