"""HQR-32 SEC-02: scanner tickets are thread-local, single-use and never restored."""
import importlib
import os
from pathlib import Path
import sys
import tempfile
from threading import Event, Thread
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))


class ScannerLifetimeTests(unittest.TestCase):
    def fixture(self):
        module = importlib.import_module('s3_native_consumers')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / 'plugins/advanced-delegation'
        root.mkdir(parents=True)
        command = ('git', '-c', 'core.fsmonitor=false', '-C', str(root), 'ls-files', '-z', '--', '*.pyc', '*.pyo')
        return module, module.ProbeGuard(temporary.name), root, ('subprocess.Popen', ('git', command, None, None))

    def denied(self, module, guard, popen):
        for event, args in (('open', (os.devnull, None, os.O_RDWR)), popen):
            with self.subTest(event=event), self.assertRaises(module.UnsafeProbe):
                guard.audit(event, args)

    def test_another_thread_cannot_spend_the_scanner_ticket_or_open_its_sink(self):
        module, guard, root, popen = self.fixture()
        observed = []
        def other():
            for event, args in (('open', (os.devnull, None, os.O_RDWR)), popen):
                try:
                    guard.audit(event, args)
                except module.UnsafeProbe:
                    observed.append('denied')
                else:
                    observed.append('admitted')
        with guard.scanner_git(root):
            thread = Thread(target=other)
            thread.start()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(observed, ['denied', 'denied'])
            guard.audit(*popen)

    def test_the_same_ticket_cannot_launch_twice_or_reopen_devnull(self):
        module, guard, root, popen = self.fixture()
        with guard.scanner_git(root):
            guard.audit('open', (os.devnull, None, os.O_RDWR))
            guard.audit(*popen)
            self.denied(module, guard, popen)
        self.denied(module, guard, popen)

    def test_nested_exit_does_not_restore_the_outer_ticket(self):
        module, guard, root, popen = self.fixture()
        with guard.scanner_git(root):
            with guard.scanner_git(root):
                guard.audit(*popen)
            self.denied(module, guard, popen)
        self.denied(module, guard, popen)

    def interleaved_exit(self, *, exceptional):
        module, guard, root, popen = self.fixture()
        outer, inner = guard.scanner_git(root), guard.scanner_git(root)
        outer.__enter__()
        inner.__enter__()
        try:
            outer.__exit__(None, None, None)
            self.denied(module, guard, popen)
        finally:
            failure = RuntimeError('synthetic interleaved exit') if exceptional else None
            inner.__exit__(RuntimeError if exceptional else None, failure, None)
        self.denied(module, guard, popen)
        # A newly requested, independent ticket is still usable after revocation.
        with guard.scanner_git(root):
            guard.audit(*popen)

    def test_interleaved_normal_exits_do_not_resurrect_a_ticket(self):
        self.interleaved_exit(exceptional=False)

    def test_interleaved_exception_exit_does_not_resurrect_a_ticket(self):
        self.interleaved_exit(exceptional=True)

    def test_overlapping_thread_scopes_do_not_revoke_or_restore_each_other(self):
        module, guard, root, popen = self.fixture()
        entered, outer_exited = Event(), Event()
        observations = []
        def second():
            try:
                with guard.scanner_git(root):
                    entered.set()
                    if not outer_exited.wait(5):
                        raise AssertionError('first scope did not exit')
                    guard.audit(*popen)
                    observations.append('admitted')
            except BaseException as exc:
                observations.append(type(exc).__name__)
        with guard.scanner_git(root):
            thread = Thread(target=second)
            thread.start()
            ready = entered.wait(5)
        outer_exited.set()
        thread.join(5)
        self.assertTrue(ready)
        self.assertFalse(thread.is_alive())
        self.assertEqual(observations, ['admitted'])
        self.denied(module, guard, popen)
