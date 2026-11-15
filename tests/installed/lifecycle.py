"""Drive the installed S1 lifecycle on the admitted Docker target and record receipts.

Usage: HQR_DOCKER_CLIENT=<client dir> HQR_PRODUCTION_HERMES_HOME=<working Hermes home> python3 tests/installed/lifecycle.py <new receipt dir>
The working Hermes is only observed by reading files; its launcher is never started.
The target container `hqr-s1-test` must already hold the candidate installed and enabled.
Every step asserts its observations and the run stops at the first failure.
The target has internet egress for native package installs but no host path, credential, account or inference.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

TARGET = "hqr-s1-test"
PLUGIN = "hermes-quota-router"
CANDIDATE = "ad3e180f32adea3c25a2ef91280f1f6308729a47"
ROLLBACK = "a8ee907efa27420fdefb35be5bcb95df6502ba8c"
ORIGIN = "gcunharodrigues/hermes-quota-router"
GITHUB = "https://github.com/gcunharodrigues/hermes-quota-router.git"
PY = "/opt/hermes-venv/bin/python"
HERMES = "/opt/hermes-venv/bin/hermes"
ROOT = Path(__file__).resolve().parents[2]

PROBE = r'''
import json, sys
calls = json.loads(sys.argv[1])
events = []
from hermes_cli.plugins import get_plugin_command_handler, resolve_plugin_command_result
from hermes_cli.plugin_command_dispatch import invoke_plugin_command
handler = get_plugin_command_handler("quota-router")
watched = ("socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "urllib.Request", "http.client.connect")
sys.addaudithook(lambda event, args: events.append(event) if event in watched else None)
results = []
for raw in calls if handler else []:
    before = len(events)
    value = resolve_plugin_command_result(invoke_plugin_command(handler, raw, source=None, session_id="", session_key="", platform="cli"))
    results.append({"args": raw, "result": json.loads(value) if value else None, "watched_events": events[before:]})
modules = {name: getattr(module, "__file__", None) for name, module in sys.modules.items() if name.startswith("hermes_plugins.hermes_quota_router")}
print(json.dumps({"handler": handler is not None, "handler_module": getattr(handler, "__module__", None), "modules": modules, "results": results}, sort_keys=True))
'''

CONFIG = r'''
import hashlib, json
from hermes_cli.config import load_config_readonly
data = load_config_readonly() or {}
plugins = data.get("plugins") or {}
entry = (plugins.get("entries") or {}).get("hermes-quota-router")
other = json.loads(json.dumps(data, default=str))
(other.get("plugins") or {}).get("entries", {}).pop("hermes-quota-router", None)
for key in ("enabled", "disabled"):
    names = (other.get("plugins") or {}).get(key)
    if isinstance(names, list):
        other["plugins"][key] = [n for n in names if n != "hermes-quota-router"]
print(json.dumps({"entry": entry, "enabled": plugins.get("enabled"), "disabled": plugins.get("disabled"), "rest_sha256": hashlib.sha256(json.dumps(other, sort_keys=True).encode()).hexdigest()}, sort_keys=True, default=str))
'''

TREE = r'''
import hashlib, json, pathlib, subprocess, sys
expected = json.loads(sys.stdin.read())
root = pathlib.Path("/home/hqr/state/plugins/hermes-quota-router")
out = {"exists": root.is_dir(), "root_is_symlink": root.is_symlink()}
if root.is_dir() and not root.is_symlink():
    actual, special = {}, []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if relative.parts[0] == ".git":
            continue
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            special.append(str(relative))
        elif path.is_file():
            actual[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    out["missing"] = sorted(expected.keys() - actual.keys())
    out["extra"] = sorted(actual.keys() - expected.keys())
    out["modified"] = sorted(p for p in expected.keys() & actual.keys() if expected[p] != actual[p])
    out["special"] = special
    out["files"] = len(actual)
    out["head"] = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    meta = pathlib.Path("/home/hqr/state/plugins/.install-metadata.json")
    out["metadata"] = json.loads(meta.read_text()).get(root.name) if meta.exists() else None
print(json.dumps(out, sort_keys=True))
'''

SCAN = r'''
import hashlib, json, pathlib, subprocess, sys, tempfile
revision, expected = sys.argv[1], json.loads(sys.stdin.read())
root = pathlib.Path(tempfile.mkdtemp(prefix="hqr-scan-")) / "hermes-quota-router"
root.mkdir()
archive = subprocess.run(["git", "-C", "/home/hqr/public-mirror.git", "archive", revision], check=True, capture_output=True).stdout
subprocess.run(["tar", "-x", "-C", str(root)], input=archive, check=True)
actual = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
from hermes_cli.config import load_config_readonly
from tools.plugin_guard import scan_plugin
result = scan_plugin(root, source=revision)
enabled = ((load_config_readonly() or {}).get("plugins") or {}).get("scan_on_install", True)
print(json.dumps({"bytes_match": actual == expected, "files": len(actual), "verdict": result.verdict, "findings": len(result.findings), "finding_ids": sorted({getattr(f, "pattern_id", "?") for f in result.findings}), "scan_on_install": enabled}, sort_keys=True))
'''

ISOLATION = r'''
import json, os, socket, sys
host = json.loads(sys.argv[1])
out = {"uid": os.getuid(), "gid": os.getgid()}
status = dict(line.split(":", 1) for line in open("/proc/self/status").read().splitlines() if ":" in line)
out["CapEff"] = status["CapEff"].strip()
out["NoNewPrivs"] = status["NoNewPrivs"].strip()
out["namespaces"] = {n: os.readlink(f"/proc/self/ns/{n}") for n in ("mnt", "net", "pid", "user", "ipc", "uts")}
out["host_paths_present"] = [p for p in host["paths"] if os.path.lexists(p)]
try:
    sys.path.insert(0, host["module_dir"])
    __import__(host["module"])
    out["host_module_imported"] = True
except ImportError:
    out["host_module_imported"] = False
def attempt(family, address):
    s = socket.socket(family, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect(address)
        return "connected"
    except OSError as exc:
        return type(exc).__name__ + ":" + str(exc.errno)
    finally:
        s.close()
out["abstract_socket"] = attempt(socket.AF_UNIX, "\0" + host["abstract"])
out["host_tcp"] = {f"{ip}:{port}": attempt(socket.AF_INET, (ip, port)) for ip in host["host_ips"] for port in host["host_ports"]}
out["synthetic_loopback_listener"] = {f"{ip}:{host['synthetic_port']}": attempt(socket.AF_INET, (ip, host["synthetic_port"])) for ip in ["127.0.0.1", *host["host_ips"]]}
out["synthetic_gateway_listener"] = attempt(socket.AF_INET, (host["gateway"], host["gateway_port"]))
out["internet_positive_control"] = attempt(socket.AF_INET, (socket.getaddrinfo("pypi.org", 443, socket.AF_INET)[0][4][0], 443))
out["docker_socket_present"] = os.path.lexists("/var/run/docker.sock")
out["environment_names"] = sorted(os.environ)
names = {"auth.json", ".env", "id_rsa", "id_ed25519", "credentials", ".netrc", ".git-credentials"}
out["credential_named_files"] = sorted(str(os.path.join(d, f)) for base in ("/home/hqr", "/opt/hermes-venv", "/tmp") for d, _, fs in os.walk(base) for f in fs if f in names)
probe = "/home/hqr/hqr-positive-control.txt"
open(probe, "w").write("synthetic")
out["guest_positive_control"] = open(probe).read() == "synthetic"
os.remove(probe)
interfaces = sorted(os.listdir("/sys/class/net"))
out["interfaces"] = interfaces
print(json.dumps(out, sort_keys=True))
'''


class Failure(Exception):
    pass


class Run:
    def __init__(self, receipts):
        self.receipts = Path(receipts)
        if self.receipts.exists() and any(self.receipts.iterdir()):
            raise Failure(f"receipt directory already used: {self.receipts}")
        self.receipts.mkdir(parents=True, exist_ok=True)
        client = Path(os.environ["HQR_DOCKER_CLIENT"])
        self.env = {"PATH": "/usr/bin:/bin", "HOME": str(client / "home"), "DOCKER_CONFIG": str(client / "docker"), "DOCKER_HOST": "unix:///var/run/docker.sock"}
        self.index = 0
        self.log = []

    def docker(self, *args, stdin=None, check=True):
        proc = subprocess.run(["docker", *args], env=self.env, input=stdin, text=True, capture_output=True, timeout=900)
        record = {"argv": ["docker", *args], "exit": proc.returncode, "stdout": proc.stdout[-6000:], "stderr": proc.stderr[-6000:]}
        self.log.append(record)
        if check and proc.returncode != 0:
            raise Failure(f"command failed: {args} -> {proc.returncode}: {proc.stderr[-800:]} {proc.stdout[-800:]}")
        return proc

    def exec(self, *argv, stdin=None, check=True):
        return self.docker("exec", "-i", TARGET, *argv, stdin=stdin, check=check)

    def hermes(self, *argv, check=True):
        return self.exec(HERMES, *argv, check=check)

    def json(self, script, *argv, stdin=None):
        out = self.exec(PY, "-I", "-B", "-c", script, *argv, stdin=stdin).stdout.strip().splitlines()[-1]
        return json.loads(out)

    def probe(self, *calls):
        return self.json(PROBE, json.dumps(list(calls)))

    def config(self):
        return self.json(CONFIG)

    def expected(self, revision):
        names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", revision], cwd=ROOT, text=True).splitlines()
        return {n: hashlib.sha256(subprocess.check_output(["git", "show", f"{revision}:{n}"], cwd=ROOT)).hexdigest() for n in names}

    def tree(self, revision, source):
        tree = self.json(TREE, stdin=json.dumps(self.expected(revision)))
        check(tree["exists"] and not tree["root_is_symlink"], "installed tree missing or symlink", tree)
        check(not (tree["missing"] or tree["extra"] or tree["modified"] or tree["special"]), "installed bytes differ from revision", tree)
        check(tree["head"] == revision, "installed HEAD differs", tree)
        meta = tree["metadata"] or {}
        check(meta.get("revision") == revision and meta.get("pinned") is True and meta.get("source") == source, "install metadata differs", tree)
        return tree

    def step(self, name, function):
        self.index += 1
        self.log = []
        started = time.time()
        record = {"step": self.index, "name": name, "started": started}
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
        record["seconds"] = round(time.time() - started, 2)
        path = self.receipts / f"{self.index:02d}-{name}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        print(f"{'PASS' if record['pass'] else 'FAIL'} {self.index:02d} {name}", flush=True)
        if not record["pass"]:
            raise SystemExit(1)
        return record["observed"]


def check(condition, message, observed=None):
    if not condition:
        raise Failure(message + (": " + json.dumps(observed, sort_keys=True, default=str)[:3000] if observed is not None else ""))


def single(result):
    check(len(result["results"]) == 1, "unexpected probe result count", result)
    item = result["results"][0]
    check(item["watched_events"] == [], "plugin command emitted network/subprocess audit events", item)
    return item["result"]


def deployment(revision):
    return json.dumps({"schema": 1, "environment": "test", "channel": "candidate", "revision": revision, "origin": ORIGIN})


def installed_modules(result):
    files = [f for f in result["modules"].values() if f]
    check(files and all(f.startswith("/home/hqr/state/plugins/hermes-quota-router/") for f in files), "handler not loaded from installed tree", result)
    check(result["handler_module"] == "hermes_plugins.hermes_quota_router.quota_router.lifecycle", "unexpected handler module", result)


def sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise Failure(f"production observation failed: {exc}") from exc


def git_head(checkout):
    git = Path(checkout) / ".git"
    try:
        if git.is_file():
            git = Path(checkout) / git.read_text().split(":", 1)[1].strip()
        head = (git / "HEAD").read_text().strip()
        if not head.startswith("ref: "):
            return head
        ref = head[5:]
        if (git / ref).is_file():
            return (git / ref).read_text().strip()
        for line in (git / "packed-refs").read_text().splitlines():
            if line.endswith(" " + ref):
                return line.split()[0]
    except OSError as exc:
        raise Failure(f"production observation failed: {exc}") from exc
    raise Failure(f"production observation failed: unresolved {ref}")


def host_state(home):
    """Fingerprint the working Hermes by reading files only; never start its launcher."""
    home = Path(home)
    plugins = home / "plugins"
    installs = {}
    try:
        for install in sorted((home / "installs").iterdir()):
            if install.is_dir():
                installs[install.name] = {
                    "facts_sha256": sha256(install / "facts.json") if (install / "facts.json").exists() else None,
                    "environments": sorted(p.name for p in (install / "environments").iterdir()) if (install / "environments").is_dir() else [],
                }
        plugin_names = sorted(p.name for p in plugins.iterdir())
    except OSError as exc:
        raise Failure(f"production observation failed: {exc}") from exc
    return {
        "head": git_head(home / "hermes-agent"),
        "uv_lock_sha256": sha256(home / "hermes-agent" / "uv.lock"),
        "config_sha256": sha256(home / "config.yaml"),
        "plugins": plugin_names,
        "plugins_metadata_sha256": sha256(plugins / ".install-metadata.json") if (plugins / ".install-metadata.json").exists() else None,
        "installs": installs,
    }


def non_loopback(lines):
    """Local addresses of `ss -l...H` listeners that are not bound to loopback."""
    found = []
    for line in lines:
        fields = line.split()
        if len(fields) < 5:
            continue
        local = fields[3]
        address = local.rsplit(":", 1)[0]
        if address.startswith("127.") or address == "[::1]" or "%lo" in address:
            continue
        found.append(local)
    return found


DHCP_CLIENT = re.compile(r"^\d{1,3}(\.\d{1,3}){3}%[^:\s]+:68$")


def unexpected_listeners(tcp_lines, udp_lines):
    """Non-loopback listeners, except an interface-scoped IPv4 DHCP client socket (UDP 68)."""
    return non_loopback(tcp_lines) + [local for local in non_loopback(udp_lines) if not DHCP_CLIENT.match(local)]


def listener_admission():
    """Fail when a host listener other than the DHCP client is bound beyond loopback."""
    tcp = subprocess.check_output(["ss", "-ltnH"], text=True).split("\n")
    udp = subprocess.check_output(["ss", "-lunH"], text=True).split("\n")
    exposed = unexpected_listeners(tcp, udp)
    check(exposed == [], "a host listener is bound beyond loopback and would be reachable from the target", exposed)
    return {"tcp": [line for line in tcp if line.strip()], "udp": [line for line in udp if line.strip()], "exposed": exposed}


def require_safe_scan(scan):
    if scan.get("verdict") != "safe":
        raise Failure(f"native scanner verdict is not safe: {json.dumps(scan, sort_keys=True)}")


def main():
    production = os.environ.get("HQR_PRODUCTION_HERMES_HOME")
    if not production:
        raise SystemExit("HQR_PRODUCTION_HERMES_HOME is required")
    production = Path(production)
    run = Run(sys.argv[1])
    host_before = run.step("host-production-before", lambda: host_state(production))

    def preconditions():
        inspect = json.loads(run.docker("inspect", TARGET).stdout)[0]
        mounts = inspect["Mounts"]
        state_only = len(mounts) == 1 and mounts[0]["Type"] == "volume" and mounts[0]["Name"] == "hqr-s1-state-net" and mounts[0]["Destination"] == "/home/hqr/state"
        check(inspect["HostConfig"]["NetworkMode"] == "bridge" and not inspect["HostConfig"]["PortBindings"] and state_only and inspect["HostConfig"]["Binds"] in (None, ["hqr-s1-state-net:/home/hqr/state"]), "target network/ports differ or it mounts more than the task state volume", mounts)
        check(inspect["Config"]["User"] == "10001:10001" and inspect["HostConfig"]["CapDrop"] == ["ALL"], "target identity/caps differ")
        tree = run.tree(CANDIDATE, GITHUB)
        result = run.probe()
        check(result["handler"], "plugin not enabled before lifecycle", result)
        installed_modules(result)
        return {"container": inspect["Id"], "image": inspect["Image"], "tree": tree, "consumer": result}
    run.step("preconditions", preconditions)

    def network_admission():
        inspect = json.loads(run.docker("inspect", TARGET).stdout)[0]
        policy = {
            "network_mode": inspect["HostConfig"]["NetworkMode"],
            "networks": sorted(inspect["NetworkSettings"]["Networks"]),
            "port_bindings": inspect["HostConfig"]["PortBindings"],
            "publish_all_ports": inspect["HostConfig"]["PublishAllPorts"],
            "cap_drop": inspect["HostConfig"]["CapDrop"],
            "cap_add": inspect["HostConfig"]["CapAdd"],
            "security_opt": inspect["HostConfig"]["SecurityOpt"],
            "privileged": inspect["HostConfig"]["Privileged"],
            "pid_mode": inspect["HostConfig"]["PidMode"],
            "ipc_mode": inspect["HostConfig"]["IpcMode"],
            "user": inspect["Config"]["User"],
            "mounts": [{k: m.get(k) for k in ("Type", "Name", "Destination", "RW")} for m in inspect["Mounts"]],
        }
        check(policy["network_mode"] == "bridge" and policy["networks"] == ["bridge"] and not policy["port_bindings"] and not policy["publish_all_ports"], "target network policy differs", policy)
        check(policy["cap_drop"] == ["ALL"] and not policy["cap_add"] and not policy["privileged"] and "no-new-privileges=true" in (policy["security_opt"] or []), "target privilege policy differs", policy)
        check(policy["pid_mode"] != "host" and policy["ipc_mode"] != "host", "target shares a host namespace", policy)
        return {"policy": policy, "listeners": listener_admission()}
    run.step("network-admission-before-mutation", network_admission)

    def declare():
        run.hermes("config", "set", f"plugins.entries.{PLUGIN}.settings.deployment", deployment(CANDIDATE))
        status = single(run.probe("status"))
        check(status["deployment"]["revision"] == CANDIDATE and status["identity_evidence"] == "declared_not_verified", "deployment not visible", status)
        check(status["mode_effective"] == "off" and status["mode_saved"] == "off" and status["ok"], "initial state not OFF", status)
        check(status["quota"] == {"state": "unknown", "source": None} and not status["auto_available"], "quota/auto not unknown/unavailable", status)
        return status
    run.step("declare-and-initial-off", declare)

    def mutable_declarations():
        seen = {}
        for label, value in (("branch", "main"), ("short", CANDIDATE[:12])):
            run.hermes("config", "set", f"plugins.entries.{PLUGIN}.settings.deployment", deployment(value))
            seen[label] = single(run.probe("status"))["identity_evidence"]
        production = json.loads(deployment(CANDIDATE))
        production.update(environment="production", channel="stable")
        run.hermes("config", "set", f"plugins.entries.{PLUGIN}.settings.deployment", json.dumps(production))
        seen["production"] = single(run.probe("status"))["identity_evidence"]
        run.hermes("config", "set", f"plugins.entries.{PLUGIN}.settings.deployment", deployment(CANDIDATE))
        check(set(seen.values()) == {"invalid"}, "mutable/production declaration accepted", seen)
        check(single(run.probe("status"))["identity_evidence"] == "declared_not_verified", "valid declaration not restored")
        return seen
    run.step("refuse-mutable-and-production-declarations", mutable_declarations)

    def auto_refused():
        before = run.config()
        status = single(run.probe("mode auto"))
        after = run.config()
        check(status.get("error", "").startswith("AUTO unavailable") and not status["ok"], "AUTO not refused", status)
        check(before == after, "AUTO refusal changed configuration", {"before": before, "after": after})
        return {"status": status, "config": after}
    run.step("auto-refused-without-write", auto_refused)

    def observe():
        before = run.config()
        status = single(run.probe("mode observe"))
        after = run.config()
        check(status["mode_effective"] == "observe" and status["mode_saved"] == "observe", "Observe not effective", status)
        check(after["rest_sha256"] == before["rest_sha256"], "Observe changed configuration outside the plugin entry", {"before": before, "after": after})
        changed = {k for k in set(before["entry"]["settings"]) | set(after["entry"]["settings"]) if before["entry"]["settings"].get(k) != after["entry"]["settings"].get(k)}
        check(changed == {"mode"}, "Observe changed plugin settings other than mode", {"before": before, "after": after})
        fresh = run.probe("status", "explain")
        installed_modules(fresh)
        for item in fresh["results"]:
            check(item["watched_events"] == [] and item["result"]["mode_effective"] == "observe", "fresh consumer does not see Observe", fresh)
            check(item["result"]["quota_queries"] == 0 and item["result"]["extra_inferences"] == 0, "plugin counters not zero", fresh)
        return {"command": status, "fresh": fresh, "config_after": after}
    run.step("observe-without-route-or-settings-change", observe)

    def divergence():
        script = PROBE.replace('print(json.dumps(', 'import subprocess as _s\n_o = _s.run([sys.executable, "-I", "-B", "-c", sys.argv[2], json.dumps(["mode off"])], capture_output=True, text=True)\nresults.append({"other_process": json.loads(_o.stdout.strip().splitlines()[-1])})\nresults.append({"args": "status", "result": json.loads(resolve_plugin_command_result(invoke_plugin_command(handler, "status", source=None, session_id="", session_key="", platform="cli")))})\nprint(json.dumps(', 1)
        out = run.json(script, json.dumps(["status"]), PROBE)
        first, other, last = out["results"][0]["result"], out["results"][1]["other_process"], out["results"][2]["result"]
        check(first["mode_effective"] == "observe", "loaded instance not in Observe", out)
        check(other["results"][0]["result"]["mode_effective"] == "off", "other process did not switch OFF", out)
        check(last["mode_effective"] == "observe" and last["mode_saved"] == "off" and last["restart_required"], "divergence/restart not visible", out)
        return out
    run.step("cross-process-divergence-visible", divergence)

    def restart():
        single(run.probe("mode observe"))
        run.docker("restart", TARGET)
        inspect = json.loads(run.docker("inspect", TARGET).stdout)[0]
        check(inspect["State"]["Running"] and inspect["HostConfig"]["NetworkMode"] == "bridge", "target not running on its own network after restart")
        status = single(run.probe("status"))
        check(status["mode_effective"] == "observe" and not status["restart_required"], "saved Observe not reloaded after restart", status)
        return {"started_at": inspect["State"]["StartedAt"], "status": status}
    run.step("restart-reloads-saved-observe", restart)

    def neutralize():
        status = single(run.probe("mode off"))
        check(status["mode_effective"] == "off", "OFF not effective", status)
        fresh = single(run.probe("status"))
        check(fresh["mode_effective"] == "off" and fresh["mode_saved"] == "off" and not fresh["restart_required"], "fresh consumer not OFF", fresh)
        listed = run.exec(PY, "-I", "-B", "-c", "import json,os;print(json.dumps([open(f'/proc/{p}/cmdline','rb').read().replace(b'\\0',b' ').decode() for p in os.listdir('/proc') if p.isdigit()]))")
        commands = json.loads(listed.stdout.strip().splitlines()[-1])
        consumers = [c for c in commands if "/bin/hermes" in c or "hermes_cli" in c]
        check(consumers == [], "a long-lived Hermes consumer is running", commands)
        return {"status": fresh, "processes": commands}
    run.step("off-in-all-consumers", neutralize)

    def disable():
        before = run.config()
        run.hermes("plugins", "disable", PLUGIN)
        after = run.config()
        show = run.hermes("plugins", "show", PLUGIN).stdout
        result = run.probe("status")
        check("Status: not enabled" in show or "Status: disabled" in show, "plugin still enabled", show)
        check(not result["handler"], "native consumer still resolves the handler", result)
        check(after["entry"] and after["entry"].get("settings") == before["entry"].get("settings"), "disable changed plugin settings", {"before": before, "after": after})
        run.tree(CANDIDATE, GITHUB)
        return {"show": show, "consumer": result, "config": after}
    run.step("disable-returns-native-path", disable)

    def remove():
        before = run.config()
        run.exec("cp", "/home/hqr/state/config.yaml", "/home/hqr/config-before-remove.yaml")
        run.hermes("plugins", "remove", PLUGIN)
        after = run.config()
        gone = run.exec("test", "!", "-e", "/home/hqr/state/plugins/hermes-quota-router", check=False).returncode == 0
        meta = run.exec(PY, "-I", "-B", "-c", "import json,pathlib;p=pathlib.Path('/home/hqr/state/plugins/.install-metadata.json');print(json.dumps(sorted(json.loads(p.read_text())) if p.exists() else []))").stdout.strip()
        result = run.probe("status")
        importable = run.exec(PY, "-I", "-B", "-c", "import importlib.util\ntry:\n    found = importlib.util.find_spec('hermes_plugins.hermes_quota_router') is not None\nexcept ModuleNotFoundError:\n    found = False\nprint(found)")
        check(gone and PLUGIN not in json.loads(meta), "plugin tree or metadata remains", {"gone": gone, "meta": meta})
        check(not result["handler"], "handler resolves after removal", result)
        check(after["rest_sha256"] == before["rest_sha256"], "removal changed configuration outside the plugin entry", {"before": before, "after": after})
        check(importable.stdout.strip() == "False", "removed plugin is still importable", importable.stdout)
        check(after["entry"] is None, "native removal kept the plugin configuration entry", after)
        return {"config_before": before, "config_after": after, "native_removed_plugin_entry": after["entry"] is None, "metadata": meta, "consumer": result, "importable": importable.stdout.strip()}
    run.step("remove-without-orphan", remove)

    source = GITHUB

    def refuse_mutable_ref():
        proc = run.hermes("plugins", "install", ORIGIN, "--ref", "main", "--no-enable", check=False)
        check(proc.returncode != 0, "mutable ref accepted", proc.stdout + proc.stderr)
        gone = run.exec("test", "!", "-e", "/home/hqr/state/plugins/hermes-quota-router", check=False).returncode == 0
        check(gone, "refused install left a tree")
        return {"exit": proc.returncode, "output": (proc.stdout + proc.stderr)[-1500:]}
    run.step("refuse-mutable-install-ref", refuse_mutable_ref)

    def install(revision, force=False):
        expected = run.expected(revision)
        scan = run.json(SCAN, revision, stdin=json.dumps(expected))
        check(scan["bytes_match"] and scan["scan_on_install"] is not False, "scanned bytes differ from the revision or scanning is disabled", scan)
        require_safe_scan(scan)
        argv = ["plugins", "install", ORIGIN, "--ref", revision, "--no-enable"] + (["--force"] if force else [])
        proc = run.hermes(*argv)
        tree = run.tree(revision, source)
        return {"scan": scan, "output": (proc.stdout + proc.stderr)[-2000:], "tree": tree}

    def enable_and_smoke(revision):
        run.hermes("config", "set", f"plugins.entries.{PLUGIN}.settings.deployment", deployment(revision))
        run.hermes("plugins", "enable", PLUGIN)
        result = run.probe("status")
        installed_modules(result)
        status = result["results"][0]["result"]
        check(result["results"][0]["watched_events"] == [], "status emitted audit events", result)
        check(status["deployment"]["revision"] == revision and status["mode_effective"] == "off", "smoke status mismatch", status)
        return status

    def reinstall():
        installed = install(CANDIDATE)
        show = run.hermes("plugins", "show", PLUGIN).stdout
        check("Status: not enabled" in show, "reinstall inherited an enable", show)
        return {"install": installed, "show": show, "smoke": enable_and_smoke(CANDIDATE)}
    run.step("reinstall-candidate", reinstall)

    def rollback():
        single(run.probe("mode off"))
        run.hermes("plugins", "disable", PLUGIN)
        installed = install(ROLLBACK, force=True)
        return {"install": installed, "smoke": enable_and_smoke(ROLLBACK)}
    run.step("rollback-to-previous-public-revision", rollback)

    def roll_forward():
        single(run.probe("mode off"))
        run.hermes("plugins", "disable", PLUGIN)
        installed = install(CANDIDATE, force=True)
        return {"install": installed, "smoke": enable_and_smoke(CANDIDATE)}
    run.step("return-to-candidate", roll_forward)

    def isolation():
        with tempfile.TemporaryDirectory(prefix="hqr-iso-", dir=os.environ.get("TMPDIR")) as scratch:
            sentinel = Path(scratch) / "sentinel.txt"
            nonce = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
            sentinel.write_text(nonce)
            (Path(scratch) / f"hqr_sentinel_{nonce}.py").write_text("VALUE = 1\n")
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind("\0hqr-run3-" + nonce)
            server.listen(4)
            accepted = []
            threading.Thread(target=lambda: accepted.append(server.accept()), daemon=True).start()
            admission = listener_admission()
            ports = sorted({int(line.split()[3].rsplit(":", 1)[1]) for line in admission["tcp"] if len(line.split()) >= 5 and line.split()[0] == "LISTEN"})
            loopback = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            loopback.bind(("127.0.0.1", 0))
            loopback.listen(8)
            gateway = json.loads(run.docker("inspect", TARGET).stdout)[0]["NetworkSettings"]["Networks"]["bridge"]["Gateway"]
            exposure = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            exposure.bind((gateway, 0))
            exposure.listen(8)
            addresses = subprocess.check_output(["ip", "-4", "-o", "addr", "show"], text=True).split("\n")
            ips = sorted({line.split()[3].split("/")[0] for line in addresses if line.strip()} - {"127.0.0.1"})
            host = {"paths": [scratch, str(sentinel), str(production), str(production / "hermes-agent")], "module_dir": scratch, "module": f"hqr_sentinel_{nonce}", "abstract": "hqr-run3-" + nonce, "host_ips": ips, "host_ports": ports, "synthetic_port": loopback.getsockname()[1], "gateway": gateway, "gateway_port": exposure.getsockname()[1]}
            guest = run.json(ISOLATION, json.dumps(host))
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect("\0hqr-run3-" + nonce)
            client.close()
            positive = socket.create_connection(("127.0.0.1", loopback.getsockname()[1]), timeout=3)
            positive.close()
            loopback.close()
            exposure.close()
            time.sleep(0.2)
            server.close()
            own = {n: os.readlink(f"/proc/self/ns/{n}") for n in ("mnt", "net", "pid")}
            check(sentinel.read_text() == nonce, "host sentinel changed")
        check(guest["uid"] == 10001 and guest["CapEff"] == "0000000000000000" and guest["NoNewPrivs"] == "1", "guest privileges differ", guest)
        check(guest["host_paths_present"] == [] and not guest["host_module_imported"], "host files visible in guest", guest)
        check(guest["abstract_socket"] != "connected", "guest reached a host abstract socket", guest)
        check(guest["host_tcp"] and all(v != "connected" for v in guest["host_tcp"].values()), "guest reached a host TCP listener", guest)
        check(all(v != "connected" for v in guest["synthetic_loopback_listener"].values()), "guest reached the synthetic host loopback listener", guest)
        check(guest["internet_positive_control"] == "connected", "internet positive control failed", guest)
        check(not guest["docker_socket_present"] and guest["interfaces"] == ["eth0", "lo"], "guest has engine access or unexpected interfaces", guest)
        check(guest["credential_named_files"] == [], "credential-named files in guest", guest)
        check(guest["guest_positive_control"] and len(accepted) == 1, "positive controls failed", {"guest": guest, "host_accepts": len(accepted)})
        check(all(guest["namespaces"][n] != own[n] for n in own), "guest shares a namespace with the host process", {"guest": guest["namespaces"], "host": own})
        return {"guest": guest, "host_namespaces": own, "host_positive_accepts": len(accepted), "host_listeners_checked": host["host_ports"], "host_ips_checked": host["host_ips"], "host_loopback_positive_control": "connected", "non_loopback_exposure_observed": guest["synthetic_gateway_listener"]}
    run.step("isolation-negative-and-positive-controls", isolation)

    def final():
        tree = run.tree(CANDIDATE, source)
        status = single(run.probe("status"))
        check(status["mode_effective"] == "off" and status["deployment"]["revision"] == CANDIDATE, "final state not candidate OFF", status)
        host_after = host_state(production)
        check(host_after == host_before, "production Hermes state changed during the run", {"before": host_before, "after": host_after})
        return {"tree": tree, "status": status, "host": host_after}
    run.step("final-state-and-production-unchanged", final)


if __name__ == "__main__":
    main()
