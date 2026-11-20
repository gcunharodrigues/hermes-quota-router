"""Revisão da simplificação, F4: the parallel runner fails on empty suites and modules and counts the guard exactly."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'run_tests.py'


def load_runner():
    spec = importlib.util.spec_from_file_location('hqr_run_tests_under_test', SCRIPT)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


def module_with(tests):
    body = ''.join(f'    def test_{index}(self):\n        pass\n' for index in range(tests)) or '    pass\n'
    return 'import unittest\n\n\nclass Synthetic(unittest.TestCase):\n' + body


class ParallelRunnerCountTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.runner = load_runner()
        self.runner.ROOT = Path(self.root.name)
        self.scratch = Path(self.root.name) / 'scratch'
        self.scratch.mkdir()

    def suite(self, modules, guard_tests=2):
        directory = Path(self.root.name) / 'tests' / 'unit'
        directory.mkdir(parents=True)
        if guard_tests is not None:
            (directory / (self.runner.GUARD + '.py')).write_text(module_with(guard_tests))
        for name, tests in modules.items():
            (directory / f'{name}.py').write_text(module_with(tests))

    def run_suite(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = self.runner.run_parallel(['unit'], 2, str(self.scratch))
        return code, output.getvalue()

    def test_a_guard_with_two_tests_is_not_counted_as_the_modules_own(self):
        self.suite({'test_a': 3})
        code, output = self.run_suite()
        self.assertEqual(code, 0, output)
        self.assertIn('Ran 5 tests in 2 modules', output)

    def test_a_suite_without_modules_fails(self):
        self.suite({}, guard_tests=None)
        code, output = self.run_suite()
        self.assertEqual(code, 1, output)
        self.assertIn('no test modules', output)

    def test_a_suite_without_tests_fails(self):
        self.suite({'test_a': 0}, guard_tests=0)
        code, output = self.run_suite()
        self.assertEqual(code, 1, output)
        self.assertIn('no tests', output)

    def test_a_module_that_runs_none_of_its_own_tests_fails_and_is_named(self):
        self.suite({'test_a': 2, 'test_empty': 0})
        code, output = self.run_suite()
        self.assertEqual(code, 1, output)
        self.assertIn('test_empty ran 0 own tests', output)


if __name__ == '__main__':
    unittest.main()
