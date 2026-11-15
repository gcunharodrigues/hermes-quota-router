"""S2 Observe through the native-source adapter over a host-shaped profile folder: no file changes (AC-17, TE-09).

The stand-in host modules expose only the pure raw-document reader; any mutating native loader fails the test.
The installed run on a real host (TE-10) remains the qualification of the host side.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "unit"))

from s2_fakes import NOW, claude, codex, reader_for  # noqa: E402
from quota_router.lifecycle import Management  # noqa: E402


def tree(base):
    found = {}
    for path in sorted(base.rglob("*")):
        stat = path.stat()
        found[str(path.relative_to(base))] = (path.is_dir(), stat.st_mode, stat.st_mtime_ns,
                                             hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)
    return found


def host(home):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("mutating native loader called")

    def read_config_doc(path):
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    config = types.ModuleType("hermes_cli.config")
    config.get_config_path = lambda: home / "config.yaml"
    config.read_raw_config = config.load_config_readonly = config.load_config = forbidden
    backend = types.ModuleType("hermes_cli.config_backend")
    backend.read_config_doc = read_config_doc
    jobs = types.ModuleType("cron.jobs")
    jobs.load_jobs = jobs.save_jobs = forbidden
    return {"hermes_cli": types.ModuleType("hermes_cli"), "hermes_cli.config": config, "hermes_cli.config_backend": backend,
            "cron": types.ModuleType("cron"), "cron.jobs": jobs}


class Context:
    def __init__(self):
        self.settings = {"mode": "observe"}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def set_config(self, key, value):
        self.settings[key] = value


CONFIG = {"model": {"provider": "openai-codex", "default": "gpt-6.1-sol"}, "agent": {"reasoning_effort": "xhigh"},
          "delegation": {"provider": "openai-codex", "model": "gpt-6.1-terra", "reasoning_effort": "medium",
                         "backends": {"model_map": {"options": [{"name": "general"}]}}}}


class NoWriteTests(unittest.TestCase):
    def run_commands(self, config_text):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "cron").mkdir()
            (home / "config.yaml").write_text(config_text, encoding="utf-8")
            (home / "cron" / "jobs.json").write_text(json.dumps([{"id": "legacy", "model": "gpt-6.1-terra"}]), encoding="utf-8")
            before = tree(home)
            ctx = Context()
            reader = reader_for(openai_codex=codex(100), anthropic=claude(10))
            with mock.patch.dict(sys.modules, host(home)):
                m = Management(ctx, importer=lambda: reader, clock=lambda: NOW)
                results = [json.loads(m.command(c + " --json")) for c in
                           ("status", "explain", "config", "config set credits.anthropic off", "config approve-map base", "explain")]
            self.assertEqual(tree(home), before)
            self.assertEqual(set(ctx.settings), {"mode", "credits.anthropic", "roles"} if results[4]["ok"] else {"mode", "credits.anthropic"})
            return results

    def test_observe_commands_leave_the_profile_folder_unchanged(self):
        results = self.run_commands(json.dumps(CONFIG))
        self.assertTrue(all(r["quota"]["providers"][p]["state"] == "ok" for r in results[:2] for p in ("openai-codex", "anthropic")))
        final = results[-1]["decisions"]
        self.assertEqual(final["conversation"]["state"], "decided")
        self.assertEqual(final["routes"]["general"]["choice"], "anthropic")
        self.assertEqual(final["cron"]["state"], "blocked_partial_pins")

    def test_malformed_config_is_unavailable_and_unchanged(self):
        results = self.run_commands("{not json")
        self.assertEqual(results[1]["decisions"]["state"], "inventory_unavailable")
        self.assertFalse(results[4]["ok"])


if __name__ == "__main__":
    unittest.main()
