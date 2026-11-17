"""Native cron/parser regressions; external Python dependencies are supplied, never installed."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
for suffix in ('', 'tests/unit', 'tests/installed'):
    sys.path.insert(0, str(ROOT / suffix))
from s3_native_consumers import ConsumerProbe, NativeHost, ProbeGuard
from s3_fakes import CONFIG, qualified
from test_s3_lifecycle import AutoContext
from s2_fakes import NOW, codex, claude, reader_for
from quota_router.apply import NativeBackend
from quota_router.lifecycle import Management
from quota_router.inventory import cron_origins, read_jobs_file


class NativeReviewTests(unittest.TestCase):
    def test_native_worker_keeps_default_home_when_process_has_another_home(self):
        from hermes_constants import get_hermes_home, set_hermes_home_override, reset_hermes_home_override
        from quota_router.events import HookWorker
        from threading import Event
        process_home = get_hermes_home()
        owner = process_home / 'default-owner'
        owner.mkdir(mode=0o700)
        seen, ready = [], Event()
        def cycle():
            seen.append(get_hermes_home())
            ready.set()
        token = set_hermes_home_override(owner)
        try:
            worker = HookWorker(None, cycle, lambda: NOW)
        finally:
            reset_hermes_home_override(token)
        try:
            worker.callback('on_session_open')()
            self.assertTrue(ready.wait(2))
            worker.wait()
            self.assertEqual(seen, [owner])
            self.assertNotEqual(seen[0], process_home)
        finally:
            worker.close()
            worker.wait()
            worker.thread.join(2)
            self.assertFalse(worker.thread.is_alive())

    def test_native_parser_competing_alias_order_matches_status(self):
        from hermes_constants import resolve_per_model_reasoning_effort
        for entries in ([('openai/gpt-6-1-terra', 'low'), ('gpt-6-1-terra', 'high')],
                        [('gpt-6-1-terra', 'high'), ('openai/gpt-6-1-terra', 'low')]):
            config = {'model': {'default': 'gpt-6.1-terra'}, 'agent': {'reasoning_overrides': dict(entries)}}
            expected = resolve_per_model_reasoning_effort('gpt-6.1-terra', dict(entries))
            self.assertEqual(cron_origins(config, [])['default']['effort']['value'], expected['effort'])
            self.assertEqual(expected['effort'], 'high')

    def test_complete_and_partial_job_pins_through_native_resolution(self):
        from hermes_cli.config_backend import Changes, write_changes
        home = Path(os.environ['HERMES_HOME'])
        path = home / 'config.yaml'
        write_changes(path, Changes(document=copy.deepcopy(CONFIG)))
        backend = NativeBackend(path)
        manager = Management(AutoContext(), backend=backend, data_dir=home / 'data', compatible=qualified,
                             importer=lambda: reader_for(openai_codex=codex(100), anthropic=claude(10)),
                             sources=lambda: (backend.read(), read_jobs_file(home / 'cron/jobs.json')),
                             profile=lambda: 'default', clock=lambda: NOW, catalogs=lambda: {})
        self.addCleanup(manager.close)
        manager.command('config approve-map base --json')
        manager.command('mode auto --json')
        probe = object.__new__(ConsumerProbe)
        probe.home = home
        probe.native = NativeHost()
        expected = {'provider': 'anthropic', 'model': 'claude-opus-5-5', 'effort': 'high'}
        for partial in (False, True):
            result = probe.cron_jobs(expected, manager.status, partial=partial)
            self.assertTrue(result['jobs_unchanged'])


if __name__ == '__main__':
    home = Path(os.environ['HERMES_HOME']).resolve(strict=True)
    guard = ProbeGuard(home, missing_credentials=True)
    os.open = guard.wrap_open(os.open)
    sys.addaudithook(guard.audit)
    unittest.main()
