#!/usr/bin/env python3
"""Supported test entry: runs suites or selected tests in a clean environment that cannot reach the native Hermes reader.

Usage, from the worktree root:
  python3 scripts/run_tests.py                      # unit, integration and harness
  python3 scripts/run_tests.py unit                 # one suite
  python3 scripts/run_tests.py tests.unit.test_modes  # selected test module, class or method
  python3 scripts/run_tests.py -j 1 unit            # one verbose discovery process per suite (the former runner)
Exit 2 when `agent.account_usage` is importable in the clean environment; no test runs in that case.

Suites run one process per test module, `-j` at a time (default: one per CPU), each after the suite's hermetic guard
module and with its own scratch HOME/TMPDIR; a failed module prints its full output, and each suite prints its totals.
A suite without test modules or tests, or a module that ran none of its own tests besides the guard's, fails the run.
Scratch lives in the user's private runtime directory (memory-backed) when there is one, else in TMPDIR.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SUITES = ("unit", "integration", "harness")
GUARD = "test_0_hermetic_environment"
PROBE = """
import importlib.util, sys
try:
    found = importlib.util.find_spec("agent.account_usage") is not None
except ImportError:
    found = False
sys.exit(3 if found else 0)
"""
RAN = re.compile(r"^Ran (\d+) tests? in ", re.M)
# Verbose result lines name each test as `method (module.Class.method)`; the guard's own tests are counted, not assumed.
TEST_ID = re.compile(r"^\w+ \(([\w.]+)\)", re.M)
STATUS = re.compile(r"^(OK|FAILED)(?: \((.*)\))?$", re.M)


def clean_env(scratch):
    return {"PATH": "/usr/bin:/bin", "HOME": scratch, "TMPDIR": scratch, "PYTHONPYCACHEPREFIX": os.path.join(scratch, "pyc")}


def run_module(suite, module, scratch):
    """One test module, after the suite's guard module, with a private HOME/TMPDIR; returns its outcome."""
    private = tempfile.mkdtemp(prefix=module[:40] + "-", dir=scratch)
    env = dict(clean_env(private), PYTHONPYCACHEPREFIX=os.path.join(scratch, "pyc"),
               PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "tests" / suite)]))
    guarded = module != GUARD and (ROOT / "tests" / suite / (GUARD + ".py")).is_file()
    started = time.monotonic()
    done = subprocess.run([sys.executable, "-m", "unittest", "-v", *([GUARD] if guarded else []), module], cwd=ROOT, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    ran, status = RAN.search(done.stdout), STATUS.findall(done.stdout)
    counts = dict((key, int(value)) for key, value in re.findall(r"([a-z ]+)=(\d+)", status[-1][1])) if status else {}
    ok = done.returncode == 0 and ran is not None and bool(status) and status[-1][0] == "OK"
    guard_tests = len({test for test in TEST_ID.findall(done.stdout) if test.startswith(GUARD + ".")}) if guarded else 0
    tests = int(ran.group(1)) - guard_tests if ran else 0
    return {"suite": suite, "module": module, "ok": ok, "code": done.returncode, "tests": tests, "counts": counts,
            "output": done.stdout, "seconds": time.monotonic() - started}


def run_parallel(suites, jobs, scratch):
    # Largest modules first, so the longest ones do not start last.
    tasks = sorted(((suite, path.stem, path.stat().st_size) for suite in suites
                    for path in (ROOT / "tests" / suite).glob("test_*.py")), key=lambda task: -task[2])
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda task: run_module(task[0], task[1], scratch), tasks))
    wall = time.monotonic() - started
    failed = False
    for suite in suites:
        mine = sorted((r for r in results if r["suite"] == suite), key=lambda r: r["module"])
        totals = {}
        for result in mine:
            for key, value in result["counts"].items():
                totals[key] = totals.get(key, 0) + value
            if not result["ok"]:
                failed = True
                print(f"== {suite}: {result['module']} failed (exit {result['code']})\n{result['output']}", flush=True)
        broken = [r["module"] for r in mine if not r["ok"]]
        # Revisão da simplificação, F4: an empty suite or a module that ran none of its own tests is a failure.
        empty = [r["module"] for r in mine if r["ok"] and r["tests"] == 0]
        for module in empty:
            print(f"== {suite}: {module} ran 0 own tests", flush=True)
        problems = broken + empty
        if not mine:
            problems.append("no test modules")
        elif sum(r["tests"] for r in mine) == 0:
            problems.append("no tests")
        failed = failed or bool(problems)
        print(f"== {suite}")
        print(f"Ran {sum(r['tests'] for r in mine)} tests in {len(mine)} modules ({jobs} processes, {wall:.1f} s wall for all suites)")
        detail = ", ".join(f"{key}={value}" for key, value in sorted(totals.items()))
        print(("FAILED: " + ", ".join(problems) if problems else "OK") + (f" ({detail})" if detail else ""), flush=True)
    slowest = sorted(results, key=lambda r: -r["seconds"])[:3]
    print("Slowest modules: " + ", ".join(f"{r['suite']}.{r['module']} {r['seconds']:.1f} s" for r in slowest), flush=True)
    return 1 if failed else 0


def scratch_parent():
    """The user's private runtime directory when it is one (memory-backed, so the many fsyncs are cheap), else TMPDIR."""
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.geteuid()}")
    try:
        info = runtime.lstat()
    except OSError:
        return None
    private = runtime.is_dir() and not runtime.is_symlink() and info.st_uid == os.geteuid() and info.st_mode & 0o077 == 0
    return str(runtime) if private and os.access(runtime, os.W_OK) else None


def main(argv):
    jobs = os.cpu_count() or 1
    if len(argv) >= 2 and argv[0] == "-j":
        jobs, argv = max(1, int(argv[1])), argv[2:]
    targets = argv or list(SUITES)
    with tempfile.TemporaryDirectory(prefix="hqr-tests-", dir=scratch_parent()) as scratch:
        env = clean_env(scratch)
        if subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, env=env).returncode != 0:
            sys.stderr.write("Native Hermes reader importable in the clean environment: no test was run\n")
            return 2
        if jobs > 1 and all(target in SUITES for target in targets):
            return run_parallel(targets, jobs, scratch)
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
