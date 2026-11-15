"""S2 installed probe (tests/installed/s2_probe.py) against fake JSON-default and text-default plugins; no Hermes."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/installed"))

import s2_probe  # noqa: E402

FAKE = r'''
import json, sys, types
readable = sys.argv.pop(2) == "readable"
seen = []
pkg = types.ModuleType("hermes_plugins.hermes_quota_router")
sys.modules[pkg.__name__] = pkg
if readable:
    sys.modules[pkg.__name__ + ".quota_router.render"] = types.ModuleType(pkg.__name__ + ".quota_router.render")

def handler(raw):
    seen.append(raw)
    parts = raw.split()
    if readable:
        as_json = "--json" in parts
        parts = [p for p in parts if p != "--json"]
        result = {"ok": parts in (["status"], ["mode", "off"]), "mode": "off"}
        return json.dumps(result) if as_json else "**Quota Router** texto"
    return json.dumps({"ok": parts in (["status"], ["mode", "off"]), "mode": "off"})

plugins = types.ModuleType("hermes_cli.plugins")
plugins.get_plugin_command_handler = lambda name: handler if name == "quota-router" else None
plugins.resolve_plugin_command_result = lambda value: value
dispatch = types.ModuleType("hermes_cli.plugin_command_dispatch")
dispatch.invoke_plugin_command = lambda h, raw, **kw: h(raw)
sys.modules.update({"hermes_cli": types.ModuleType("hermes_cli"), "hermes_cli.plugins": plugins,
                    "hermes_cli.plugin_command_dispatch": dispatch})
import atexit
atexit.register(lambda: sys.stderr.write(json.dumps(seen)))
'''


def run(kind, *calls):
    script = FAKE + s2_probe.PROBE
    done = subprocess.run([sys.executable, "-c", script, json.dumps(list(calls)), kind], capture_output=True, text=True, check=True)
    return json.loads(done.stdout.strip().splitlines()[-1]), json.loads(done.stderr)


class ProbeTests(unittest.TestCase):
    def test_json_default_revisions_get_the_command_unchanged(self):
        out, seen = run("legacy", "mode off", "status")
        self.assertFalse(out["readable"])
        self.assertEqual(seen, ["mode off", "status"])
        self.assertTrue(all(r["result"]["ok"] for r in out["results"]))

    def test_text_default_revisions_get_json_requested(self):
        out, seen = run("readable", "mode off", "status")
        self.assertTrue(out["readable"])
        self.assertEqual(seen, ["mode off --json", "status --json"])
        self.assertTrue(all(r["result"]["ok"] for r in out["results"]))

    def test_s1_probe_is_unchanged(self):
        from lifecycle import PROBE
        self.assertIn('invoke_plugin_command(handler, raw, source=None', PROBE)
        self.assertNotIn("--json", PROBE)


if __name__ == "__main__":
    unittest.main()
