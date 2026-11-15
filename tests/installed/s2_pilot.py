"""D1 pilot: install the reviewed S2 candidate in the working Hermes, Observe with real quota readings, rehearse removal.

Usage: python3 tests/installed/s2_pilot.py <new receipt dir> --candidate <SHA40> --runner <bootstrap runner>
`--runner` is a shell script that runs a Python file with the working Hermes bootstrap and never starts an agent.
Steps follow decisions/s2-plan.md, "Piloto no Hermes de trabalho (D1)"; the run stops at the first failure.
No gateway restart: if one were needed, the pilot stops and asks Guilherme.
Receipts hold real quota readings and stay out of Git.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lifecycle import Failure, check  # noqa: E402
from s2_probe import PROBE  # noqa: E402

HOME = Path("/home/hermes/.hermes")
PLUGIN = "hermes-quota-router"
ORIGIN = "gcunharodrigues/hermes-quota-router"
GITHUB = "https://github.com/gcunharodrigues/hermes-quota-router.git"
ROOT = Path(__file__).resolve().parents[2]
SHA40 = re.compile(r"^[0-9a-f]{40}$")
NETWORK_EVENTS = {"socket.connect", "socket.getaddrinfo", "http.client.connect", "urllib.Request"}

# Raw config document (open and parse only): plugin entry, enable lists and a hash of everything else.
RAW = r'''
import hashlib, json, sys
from hermes_cli.config_backend import read_config_doc
data = read_config_doc(sys.argv[1]) or {}
plugins = data.get("plugins") if isinstance(data.get("plugins"), dict) else {}
entry = (plugins.get("entries") or {}).pop("hermes-quota-router", None)
lists = {}
for key in ("enabled", "disabled"):
    if isinstance(plugins.get(key), list):
        lists[key] = "hermes-quota-router" in plugins[key]
        plugins[key] = [n for n in plugins[key] if n != "hermes-quota-router"]
print(json.dumps({"entry": entry, "listed": lists, "rest_sha256": hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()}, sort_keys=True, default=str))
'''

SCAN = r'''
import json, sys
from pathlib import Path
from tools.plugin_guard import scan_plugin
result = scan_plugin(Path(sys.argv[1]), source=sys.argv[2])
print(json.dumps({"verdict": result.verdict, "findings": len(result.findings), "finding_ids": sorted({getattr(f, "pattern_id", "?") for f in result.findings})}, sort_keys=True))
'''


class Pilot:
    def __init__(self, receipts, runner, candidate):
        self.receipts = Path(receipts)
        if self.receipts.exists() and any(self.receipts.iterdir()):
            raise Failure(f"receipt directory already used: {self.receipts}")
        self.receipts.mkdir(parents=True, exist_ok=True)
        self.runner, self.candidate = runner, candidate
        self.scratch = Path(tempfile.mkdtemp(prefix="hqr-pilot-", dir=os.environ.get("TMPDIR")))
        self.index, self.log = 0, []

    def run(self, argv, check_exit=True):
        proc = subprocess.run(argv, text=True, capture_output=True, timeout=900)
        self.log.append({"argv": argv, "exit": proc.returncode, "stdout": proc.stdout[-6000:], "stderr": proc.stderr[-3000:]})
        if check_exit and proc.returncode != 0:
            raise Failure(f"command failed: {argv} -> {proc.returncode}: {proc.stderr[-800:]} {proc.stdout[-800:]}")
        return proc

    def hermes(self, *argv, check_exit=True):
        return self.run(["hermes", *argv], check_exit)

    def python(self, source, *argv):
        script = self.scratch / f"script-{hashlib.sha256(source.encode()).hexdigest()[:12]}.py"
        script.write_text(source, encoding="utf-8")
        out = self.run([self.runner, str(script), *argv]).stdout.strip().splitlines()
        return json.loads(out[-1])

    def raw(self, path=HOME / "config.yaml"):
        return self.python(RAW, str(path))

    def probe(self, *calls):
        return self.python(PROBE, json.dumps(list(calls)))

    def expected(self):
        names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", self.candidate], cwd=ROOT, text=True).splitlines()
        return {n: hashlib.sha256(subprocess.check_output(["git", "show", f"{self.candidate}:{n}"], cwd=ROOT)).hexdigest() for n in names}

    def tree(self):
        root = HOME / "plugins" / PLUGIN
        check(root.is_dir() and not root.is_symlink(), "installed tree missing or symlink")
        actual = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in root.rglob("*") if p.is_file() and p.relative_to(root).parts[0] != ".git"}
        expected = self.expected()
        diff = {"missing": sorted(expected.keys() - actual.keys()), "extra": sorted(actual.keys() - expected.keys()),
                "modified": sorted(p for p in expected.keys() & actual.keys() if expected[p] != actual[p])}
        check(not any(diff.values()), "installed bytes differ from the candidate", diff)
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        meta = json.loads((HOME / "plugins" / ".install-metadata.json").read_text()).get(PLUGIN) or {}
        check(head == self.candidate and meta.get("revision") == self.candidate and meta.get("pinned") is True and meta.get("source") == GITHUB,
              "installed revision or metadata differs", {"head": head, "meta": meta})
        return {"files": len(actual), "head": head, "metadata": meta}

    def step(self, name, function):
        self.index += 1
        self.log = []
        record = {"step": self.index, "name": name, "started": time.time()}
        try:
            record["observed"] = function()
            record["pass"] = True
        except Failure as exc:
            record["pass"] = False
            record["failure"] = str(exc)
        except Exception as exc:
            record["pass"] = False
            record["failure"] = f"{type(exc).__name__}: {exc}"
        record["commands"] = self.log
        (self.receipts / f"{self.index:02d}-{name}.json").write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n")
        print(f"{'PASS' if record['pass'] else 'FAIL'} {self.index:02d} {name}", flush=True)
        if not record["pass"]:
            raise SystemExit(1)
        return record["observed"]


def results(probe):
    """Command results with the audit events each one emitted; network is the native reader, subprocess is never allowed."""
    for item in probe["results"]:
        events = set(item["watched_events"])
        check(events <= NETWORK_EVENTS, "plugin command emitted subprocess/exec audit events", item)
    return [item["result"] for item in probe["results"]]


def fingerprint():
    agent = HOME / "hermes-agent"
    head = subprocess.check_output(["git", "-C", str(agent), "rev-parse", "HEAD"], text=True).strip()
    return {"hermes_head": head, "uv_lock_sha256": hashlib.sha256((agent / "uv.lock").read_bytes()).hexdigest(),
            "plugins": sorted(p.name for p in (HOME / "plugins").iterdir())}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("receipts")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--runner", required=True)
    args = parser.parse_args(argv)
    if not SHA40.match(args.candidate):
        parser.error("--candidate must be a 40-character commit SHA")
    pilot = Pilot(args.receipts, args.runner, args.candidate)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = HOME / "backups" / f"hqr-pilot-{stamp}"

    def preflight():
        raw = pilot.raw()
        check(raw["entry"] is None and not any(raw["listed"].values()), "plugin already configured", raw)
        check(not (HOME / "plugins" / PLUGIN).exists(), "plugin already installed")
        remote = pilot.run(["git", "ls-remote", GITHUB, "refs/heads/hermes/2026-11-15-hqr-s2"]).stdout.split()
        check(remote[:1] == [args.candidate], "candidate is not the published branch head", remote)
        return {"config": raw, "host": fingerprint(), "remote": remote}
    before = pilot.step("preflight", preflight)

    def take_backup():
        backup.mkdir(parents=True)
        shutil.copy2(HOME / "config.yaml", backup / "config.yaml")
        with tarfile.open(backup / "plugins.tar.gz", "w:gz") as archive:
            archive.add(HOME / "plugins", arcname="plugins")
        sums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(backup.iterdir())}
        (backup / "SHA256SUMS").write_text("".join(f"{v}  {k}\n" for k, v in sums.items()))
        copy = pilot.raw(backup / "config.yaml")
        check(copy["rest_sha256"] == before["config"]["rest_sha256"], "backup copy differs from the live configuration", copy)
        return {"path": str(backup), "sha256": sums}
    pilot.step("dated-backup-with-hashes", take_backup)

    def scan():
        root = pilot.scratch / "candidate" / PLUGIN
        root.mkdir(parents=True)
        archive = subprocess.run(["git", "archive", args.candidate], cwd=ROOT, check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(root)], input=archive, check=True)
        result = pilot.python(SCAN, str(root), args.candidate)
        check(result["verdict"] == "safe", "native scanner verdict is not safe", result)
        return result
    pilot.step("native-scanner-safe", scan)

    def install():
        proc = pilot.hermes("plugins", "install", ORIGIN, "--ref", args.candidate, "--no-enable")
        tree = pilot.tree()
        show = pilot.hermes("plugins", "show", PLUGIN).stdout
        check("Status: not enabled" in show, "install inherited an enable", show)
        return {"output": (proc.stdout + proc.stderr)[-2000:], "tree": tree}
    pilot.step("install-candidate-disabled", install)

    def enable_off():
        pilot.hermes("plugins", "enable", PLUGIN)
        status = results(pilot.probe("status"))[0]
        check(status["mode_effective"] == "off" and status["quota"] == {"state": "unknown", "source": None} and status["quota_queries"] == 0,
              "enabled plugin not OFF without readings", status)
        raw = pilot.raw()
        check(raw["rest_sha256"] == before["config"]["rest_sha256"], "enable changed configuration outside the plugin", raw)
        return {"status": status, "config": raw}
    pilot.step("enable-shows-off", enable_off)

    def observe():
        mode = results(pilot.probe("mode observe"))[0]
        check(mode["ok"] and mode["mode_effective"] == "observe", "Observe refused", mode)
        status, explain, config = results(pilot.probe("status", "explain", "config"))
        raw = pilot.raw()
        check(raw["rest_sha256"] == before["config"]["rest_sha256"], "Observe changed configuration outside the plugin", raw)
        check(set(raw["entry"]["settings"]) == {"mode"}, "Observe saved plugin settings other than mode", raw["entry"])
        check(status["extra_inferences"] == 0 and explain["extra_inferences"] == 0 and not status["auto_available"], "inference or Auto", status)
        check(status["quota"]["source"] == "native_account_usage" and status["quota_queries"] == 2, "quota source or count differs", status)
        check(config["ok"] and config["settings"]["credits.anthropic"] is False, "settings view differs", config)
        return {"status": status, "explain": explain, "config": config, "plugin_entry": raw["entry"]}
    pilot.step("observe-with-real-quotas", observe)

    def remove():
        off = results(pilot.probe("mode off"))[0]
        fresh = results(pilot.probe("status"))[0]
        check(off["ok"] and off["mode_effective"] == "off" and fresh["mode_effective"] == "off" and not fresh["restart_required"], "OFF not effective", fresh)
        pilot.hermes("plugins", "disable", PLUGIN)
        pilot.hermes("plugins", "remove", PLUGIN)
        raw = pilot.raw()
        meta = json.loads((HOME / "plugins" / ".install-metadata.json").read_text())
        check(not (HOME / "plugins" / PLUGIN).exists() and PLUGIN not in meta, "plugin tree or metadata remains")
        check(raw["entry"] is None and not any(raw["listed"].values()), "plugin entry remains", raw)
        backup_raw = pilot.raw(backup / "config.yaml")
        check(raw["rest_sha256"] == backup_raw["rest_sha256"], "configuration differs from the backup after removal", {"live": raw, "backup": backup_raw})
        consumer = pilot.probe()
        check(not consumer["handler"], "handler resolves after removal", consumer)
        return {"config": raw, "matches_backup": True}
    pilot.step("off-disable-remove-matches-backup", remove)

    def reinstall():
        pilot.hermes("plugins", "install", ORIGIN, "--ref", args.candidate, "--no-enable")
        tree = pilot.tree()
        pilot.hermes("plugins", "enable", PLUGIN)
        mode = results(pilot.probe("mode observe"))[0]
        status = results(pilot.probe("status"))[0]
        check(mode["ok"] and status["mode_effective"] == "observe" and status["settings"]["roles"] == {}, "reinstall not in Observe from defaults", status)
        raw = pilot.raw()
        check(raw["rest_sha256"] == before["config"]["rest_sha256"], "reinstall changed configuration outside the plugin", raw)
        return {"tree": tree, "status": status}
    pilot.step("reinstall-and-keep-observe", reinstall)

    def final():
        host = fingerprint()
        check(host["hermes_head"] == before["host"]["hermes_head"] and host["uv_lock_sha256"] == before["host"]["uv_lock_sha256"],
              "Hermes checkout changed", {"before": before["host"], "after": host})
        check(sorted(set(host["plugins"]) - set(before["host"]["plugins"])) == [PLUGIN], "unexpected plugin directories", host)
        return {"host": host, "gateway_restart": "not_done_needs_authorization_to_load_the_slash_command"}
    pilot.step("final-observe-left-for-guilherme", final)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Failure as exc:
        raise SystemExit(str(exc))
