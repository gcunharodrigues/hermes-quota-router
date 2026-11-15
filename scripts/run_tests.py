#!/usr/bin/env python3
"""Supported test entry: runs suites or selected tests in a clean environment that cannot reach the native Hermes reader.

Usage, from the worktree root:
  python3 scripts/run_tests.py                      # unit, integration and harness
  python3 scripts/run_tests.py unit                 # one suite
  python3 scripts/run_tests.py tests.unit.test_modes  # selected test module, class or method
Exit 2 when `agent.account_usage` is importable in the clean environment; no test runs in that case.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SUITES = ("unit", "integration", "harness")
PROBE = """
import importlib.util, sys
try:
    found = importlib.util.find_spec("agent.account_usage") is not None
except ImportError:
    found = False
sys.exit(3 if found else 0)
"""


def main(argv):
    targets = argv or list(SUITES)
    with tempfile.TemporaryDirectory(prefix="hqr-tests-") as scratch:
        env = {"PATH": "/usr/bin:/bin", "HOME": scratch, "TMPDIR": scratch, "PYTHONPYCACHEPREFIX": os.path.join(scratch, "pyc")}
        if subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, env=env).returncode != 0:
            sys.stderr.write("Native Hermes reader importable in the clean environment: no test was run\n")
            return 2
        failed = 0
        for target in targets:
            if target in SUITES:
                args = ["-m", "unittest", "discover", "-s", f"tests/{target}", "-p", "test_*.py", "-v"]
            else:
                module = target.split(".")
                suite_dir = ROOT / "tests" / module[1] if len(module) > 2 and module[0] == "tests" else None
                extra = {"PYTHONPATH": os.pathsep.join([str(ROOT), str(suite_dir)])} if suite_dir else {}
                args = ["-m", "unittest", ".".join(module[2:]) if suite_dir else target, "-v"]
                env = dict(env, **extra)
            print(f"== {target}", flush=True)
            failed |= subprocess.run([sys.executable, *args], cwd=ROOT, env=env).returncode != 0
        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
