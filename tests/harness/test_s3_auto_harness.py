"""S3 installed-runner contract: literal revisions, ordered swaps and stop-on-failure; never calls Docker."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/installed'))


class RunnerTests(unittest.TestCase):
    def module(self):
        spec = importlib.util.find_spec('s3_auto')
        self.assertIsNotNone(spec, 'S3 installed runner is missing')
        import s3_auto
        return s3_auto

    def test_literal_distinct_full_revisions_required(self):
        runner = self.module()
        a, b = 'a' * 40, 'b' * 40
        self.assertEqual(runner.parse(['receipts', '--candidate', a, '--rollback', b]).candidate, a)
        for candidate, rollback in ((a[:12], b), ('main', b), (a.upper(), b), (a, a)):
            with self.subTest(candidate=candidate), self.assertRaises(SystemExit):
                runner.parse(['receipts', '--candidate', candidate, '--rollback', rollback])

    def test_every_swap_requires_off_disable_scan_install_files_enable_smoke(self):
        runner = self.module()
        steps = []
        callbacks = {key: (lambda revision, k=key: steps.append((k, revision)))
                     for key in ('off', 'disable', 'scan', 'install', 'files', 'enable', 'smoke')}
        runner.swap_revision('a' * 40, callbacks)
        self.assertEqual([k for k, _ in steps], ['off', 'disable', 'scan', 'install', 'files', 'enable', 'smoke'])
        self.assertTrue(all(revision == 'a' * 40 for _, revision in steps))

    def test_failed_gate_prevents_install_and_enable(self):
        runner = self.module()
        seen = []
        def refuse(_revision):
            raise RuntimeError('synthetic unsafe scanner')
        callbacks = {key: (lambda revision, k=key: seen.append(k))
                     for key in ('off', 'disable', 'scan', 'install', 'files', 'enable', 'smoke')}
        callbacks['scan'] = refuse
        with self.assertRaises(RuntimeError):
            runner.swap_revision('a' * 40, callbacks)
        self.assertEqual(seen, ['off', 'disable'])


if __name__ == '__main__':
    unittest.main()
