"""Drive the installed S2 Observe run on the admitted Docker target and record receipts.

Usage: HQR_DOCKER_CLIENT=<client dir> HQR_PRODUCTION_HERMES_HOME=<working Hermes home> \
    python3 tests/installed/s2_observe.py <new receipt dir> --candidate <SHA40> --rollback <SHA40>
The target `hqr-s1-test` must hold an earlier public revision installed and enabled; it has no credentials,
so the native quota reader must report every provider as unknown.
The working Hermes is only observed by reading files; its launcher is never started.
Every step asserts its observations and the run stops at the first failure.
`tests/installed/lifecycle.py` stays the S1 evidence; this runner reuses its helpers without changing it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lifecycle import (  # noqa: E402
    CONFIG, GITHUB, ISOLATION, ORIGIN, PLUGIN, PY, SCAN, TARGET, Failure, Run, check, deployment, host_state,
    installed_modules, listener_admission, require_safe_scan, single,
)

SHA40 = re.compile(r"^[0-9a-f]{40}$")
NEW_PROFILE = "hqr-unenrolled"
STATE = "/home/hqr/state"
VOLUME = "hqr-s1-state-net"
TASK_LABEL = "t_1c0d7681"
BACKUP_KEEP = 5  # hermes_cli/config_backups.py DEFAULT_KEEP

# Files of the target's Hermes home, excluding caches, interpreters and the plugin's own tree.
FILES = r'''
import hashlib, json, os
root = "/home/hqr/state"
skip = ("cache/", "tools/python-", "tools/uv-", "plugins/hermes-quota-router/", "audio_cache/", "image_cache/")
out = {}
for directory, _, names in os.walk(root):
    for name in names:
        path = os.path.join(directory, name)
        relative = os.path.relpath(path, root)
        if relative.startswith(skip) or "__pycache__" in relative or os.path.islink(path):
            continue
        with open(path, "rb") as handle:
            out[relative] = hashlib.sha256(handle.read()).hexdigest()
print(json.dumps(out, sort_keys=True))
'''

# Raw configuration without the plugin entry, for config.yaml and each named backup (backup provenance).
RAW_REST = r'''
import hashlib, json, sys
from hermes_cli.config_backend import read_config_doc  # open and parse only; the host venv has no PyYAML module
def rest(path):
    data = read_config_doc(path) or {}
    plugins = data.get("plugins") if isinstance(data.get("plugins"), dict) else {}
    (plugins.get("entries") or {}).pop("hermes-quota-router", None)
    for key in ("enabled", "disabled"):
        if isinstance(plugins.get(key), list):
            plugins[key] = [n for n in plugins[key] if n != "hermes-quota-router"]
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
root = "/home/hqr/state/"
print(json.dumps({p: rest(root + p) for p in ["config.yaml", *json.loads(sys.argv[1])]}, sort_keys=True))
'''

# Host-owned side effects that do not change configuration keys (docs/s2-operations.md, "Limites").
BACKUP = re.compile(r"^backups/config/config\.yaml\.good\.\d{8}-\d{6}$")
APPENDABLE = {"logs/agent.log", "logs/errors.log", ".config.yaml.lock", "auth.lock", "plugins/.install-metadata.json.lock"}


def file_changes(before, after):
    changed = sorted(p for p in before.keys() & after.keys() if before[p] != after[p])
    return {"added": sorted(after.keys() - before.keys()), "removed": sorted(before.keys() - after.keys()), "changed": changed}


def unexpected_changes(changes, after, provenance=None):
    """Paths outside the narrow host-owned set (docs/s2-operations.md); config.yaml itself is checked by key.

    Allowed: writes to the named logs and locks; a new "good" config backup whose raw content, without the plugin entry,
    equals the current configuration (`provenance[path] is True`); removal of the oldest backups by the host's rotation.
    """
    provenance = provenance or {}
    bad = [p for p in changes["changed"] if p != "config.yaml" and p not in APPENDABLE]
    added = [p for p in changes["added"] if BACKUP.match(p) and provenance.get(p) is True]
    bad += [p for p in changes["added"] if p not in APPENDABLE and p not in added]
    # The host deletes only after creating a backup, and keeps the newest BACKUP_KEEP of new plus existing.
    removed = [p for p in changes["removed"] if BACKUP.match(p)]
    bad += [p for p in changes["removed"] if p not in removed]
    remaining = sorted(p for p in after if BACKUP.match(p))
    before = sorted(set(remaining) - set(added) | set(removed))
    union = sorted(set(before) | set(added))
    keep = min(BACKUP_KEEP, len(union)) if added else len(before)
    expected = set(union[:len(union) - keep])
    if set(removed) != expected:
        bad += sorted(set(removed) ^ expected)
    return sorted(set(bad))


def inactive(show):
    """`hermes plugins show` for an installed plugin that will not load: fresh install or kept explicit disable."""
    return "Status: not enabled" in show or "Status: disabled" in show


def require_off(status, fresh):
    check(status.get("ok") is True and status["mode_effective"] == "off" and status["mode_saved"] == "off", "OFF refused", status)
    check(fresh["mode_effective"] == "off" and fresh["mode_saved"] == "off" and not fresh["restart_required"], "fresh consumer not OFF", fresh)


def settings_changed(before, after):
    old, new = (before["entry"] or {}).get("settings") or {}, (after["entry"] or {}).get("settings") or {}
    return sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))


def observe_contract(status, queries):
    """Assertions for one Observe status on a target without credentials."""
    check(status["ok"] and status["mode_effective"] == "observe", "Observe not effective", status)
    quota = status["quota"]
    check(quota["state"] == "observed" and quota["source"] == "native_account_usage", "quota source differs", quota)
    providers = quota["providers"]
    check(sorted(providers) == ["anthropic", "openai-codex"], "providers differ", providers)
    check(all(r["state"] == "unknown" and r["reason"] for r in providers.values()), "a reading counted as known without credentials", providers)
    check(status["quota_queries"] == queries and status["extra_inferences"] == 0, "query or inference counters differ", status)
    check(status["decision_incomplete"] and status["auto_available"] is False, "decision not incomplete or Auto available", status)
    return {p: r["reason"] for p, r in providers.items()}


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("receipts")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--rollback", required=True)
    args = parser.parse_args(argv)
    for name in ("candidate", "rollback"):
        if not SHA40.match(getattr(args, name)):
            parser.error(f"--{name} must be a 40-character commit SHA")
    if args.candidate == args.rollback:
        parser.error("candidate and rollback must differ")
    return args


def isolation(run, production):
    """Same negative and positive controls as the S1 runner, with S2 socket names."""
    with tempfile.TemporaryDirectory(prefix="hqr-iso-", dir=os.environ.get("TMPDIR")) as scratch:
        sentinel = Path(scratch) / "sentinel.txt"
        nonce = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        sentinel.write_text(nonce)
        (Path(scratch) / f"hqr_sentinel_{nonce}.py").write_text("VALUE = 1\n")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind("\0hqr-s2-" + nonce)
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
        host = {"paths": [scratch, str(sentinel), str(production), str(production / "hermes-agent")], "module_dir": scratch,
                "module": f"hqr_sentinel_{nonce}", "abstract": "hqr-s2-" + nonce, "host_ips": ips, "host_ports": ports,
                "synthetic_port": loopback.getsockname()[1], "gateway": gateway, "gateway_port": exposure.getsockname()[1]}
        guest = run.json(ISOLATION, json.dumps(host))
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect("\0hqr-s2-" + nonce)
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
    return {"guest": guest, "host_namespaces": own, "host_listeners_checked": host["host_ports"], "host_ips_checked": host["host_ips"],
            "non_loopback_exposure_observed": guest["synthetic_gateway_listener"]}


def main(argv):
    args = parse(argv)
    production = os.environ.get("HQR_PRODUCTION_HERMES_HOME")
    if not production:
        raise SystemExit("HQR_PRODUCTION_HERMES_HOME is required")
    production = Path(production)
    candidate, rollback = args.candidate, args.rollback
    run = Run(args.receipts)
    files = lambda: run.json(FILES)  # noqa: E731
    host_before = run.step("host-production-before", lambda: host_state(production))

    def preconditions():
        inspect = json.loads(run.docker("inspect", TARGET).stdout)[0]
        mounts = inspect["Mounts"]
        mount = mounts[0] if len(mounts) == 1 else {}
        state_only = (mount.get("Type") == "volume" and mount.get("Name") == VOLUME and mount.get("Destination") == STATE
                      and mount.get("Driver") == "local" and inspect["HostConfig"]["Binds"] in (None, [f"{VOLUME}:{STATE}"]))
        check(inspect["HostConfig"]["NetworkMode"] == "bridge" and not inspect["HostConfig"]["PortBindings"] and state_only,
              "target network/ports differ or it mounts more than the task state volume", mounts)
        volume = json.loads(run.docker("volume", "inspect", VOLUME).stdout)[0]
        check(volume["Driver"] == "local" and not volume["Options"] and (volume["Labels"] or {}).get("hqr.task") == TASK_LABEL,
              "state volume is not the task-created local volume without options", volume)
        check(inspect["Config"]["Labels"].get("hqr.task") == TASK_LABEL, "target is not the task container", inspect["Config"]["Labels"])
        check(inspect["Config"]["User"] == "10001:10001" and inspect["HostConfig"]["CapDrop"] == ["ALL"], "target identity/caps differ")
        result = run.probe()
        check(result["handler"], "plugin not enabled before the run", result)
        installed_modules(result)
        return {"container": inspect["Id"], "image": inspect["Image"], "consumer": result}
    run.step("preconditions", preconditions)

    def network_admission():
        inspect = json.loads(run.docker("inspect", TARGET).stdout)[0]
        host = inspect["HostConfig"]
        policy = {"network_mode": host["NetworkMode"], "networks": sorted(inspect["NetworkSettings"]["Networks"]),
                  "port_bindings": host["PortBindings"], "publish_all_ports": host["PublishAllPorts"], "cap_drop": host["CapDrop"],
                  "cap_add": host["CapAdd"], "security_opt": host["SecurityOpt"], "privileged": host["Privileged"],
                  "pid_mode": host["PidMode"], "ipc_mode": host["IpcMode"], "user": inspect["Config"]["User"]}
        check(policy["network_mode"] == "bridge" and policy["networks"] == ["bridge"] and not policy["port_bindings"] and not policy["publish_all_ports"],
              "target network policy differs", policy)
        check(policy["cap_drop"] == ["ALL"] and not policy["cap_add"] and not policy["privileged"] and "no-new-privileges=true" in (policy["security_opt"] or []),
              "target privilege policy differs", policy)
        check(policy["pid_mode"] != "host" and policy["ipc_mode"] != "host", "target shares a host namespace", policy)
        return {"policy": policy, "listeners": listener_admission()}
    run.step("network-admission-before-mutation", network_admission)

    def mirror():
        run.exec("git", "-C", "/home/hqr/public-mirror.git", "fetch", "--prune", "origin")
        found = {}
        for revision in (candidate, rollback):
            found[revision] = run.exec("git", "-C", "/home/hqr/public-mirror.git", "cat-file", "-t", revision, check=False).stdout.strip()
        check(set(found.values()) == {"commit"}, "candidate or rollback not published", found)
        return found
    run.step("public-mirror-has-revisions", mirror)

    def install(revision, force):
        expected = run.expected(revision)
        scan = run.json(SCAN, revision, stdin=json.dumps(expected))
        check(scan["bytes_match"] and scan["scan_on_install"] is not False, "scanned bytes differ from the revision or scanning is disabled", scan)
        require_safe_scan(scan)
        argv = ["plugins", "install", ORIGIN, "--ref", revision, "--no-enable"] + (["--force"] if force else [])
        proc = run.hermes(*argv)
        tree = run.tree(revision, GITHUB)
        show = run.hermes("plugins", "show", PLUGIN).stdout
        check(inactive(show), "install inherited an enable", show)
        consumer = run.probe("status")
        check(not consumer["handler"], "a fresh consumer resolves the handler before enable", consumer)
        return {"scan": scan, "output": (proc.stdout + proc.stderr)[-2000:], "tree": tree, "show": show}

    def neutral():
        """Effective OFF, confirmed by a fresh consumer, before any disable, replacement or removal (E2)."""
        require_off(single(run.probe("mode off")), single(run.probe("status")))
        run.hermes("plugins", "disable", PLUGIN)

    def enable_and_smoke(revision):
        run.hermes("config", "set", f"plugins.entries.{PLUGIN}.settings.deployment", deployment(revision))
        run.hermes("plugins", "enable", PLUGIN)
        result = run.probe("status")
        installed_modules(result)
        status = single(result)
        check(status["deployment"]["revision"] == revision and status["mode_effective"] == "off", "smoke status mismatch", status)
        check(status["quota"] == {"state": "unknown", "source": None} and status["quota_queries"] == 0, "OFF read quotas", status)
        return status

    def to_candidate():
        neutral()
        installed = install(candidate, force=True)
        return {"install": installed, "smoke": enable_and_smoke(candidate)}
    run.step("install-candidate-off", to_candidate)

    def off_defaults():
        status = single(run.probe("status"))
        check(status["settings"]["credits.anthropic"] is False and status["settings"]["credits.openai-codex"] is True, "credit defaults differ", status)
        check(status["settings"]["roles"] == {} and status["settings_invalid"] == {}, "roles or settings not at defaults", status)
        check(status["enrollment"]["state"] == "enrolled", "enrollment not reported", status)
        return status
    run.step("off-shows-settings-without-readings", off_defaults)

    def auto_refused():
        before, files_before = run.config(), files()
        status = single(run.probe("mode auto"))
        after, files_after = run.config(), files()
        check(status.get("error", "").startswith("AUTO unavailable") and not status["ok"], "AUTO not refused", status)
        check(before == after and files_before == files_after, "AUTO refusal changed files", file_changes(files_before, files_after))
        return status
    run.step("auto-refused-without-write", auto_refused)

    def observe():
        before, files_before = run.config(), files()
        mode = single(run.probe("mode observe"))
        result = run.probe("status", "explain", "config", "config set credits.anthropic off", "config reset limits.hysteresis_pct", "status")
        installed_modules(result)
        after, files_after = run.config(), files()
        items = [item["result"] for item in result["results"]]
        check(all(item["watched_events"] == [] for item in result["results"]), "plugin command emitted network/subprocess audit events", result)
        reasons = observe_contract(items[0], 2)
        observe_contract(items[1], 4)
        observe_contract(items[5], 6)
        decisions = items[1]["decisions"]
        check(decisions["conversation"]["choice"] is None and decisions["conversation"]["reason"] == "no_eligible_candidate", "a choice without readings", decisions)
        check(items[1]["map"]["status"] == "proposal_not_approved" and items[1]["coverage"]["inventory"] == "ok", "map or inventory differs", items[1])
        check(items[2]["ok"] and items[3]["ok"] and items[4]["ok"], "config commands failed", items[2:5])
        check(after["rest_sha256"] == before["rest_sha256"], "Observe changed configuration outside the plugin entry", {"before": before, "after": after})
        keys = settings_changed(before, after)
        check(set(keys) <= {"mode", "credits.anthropic", "limits.hysteresis_pct"}, "Observe changed other plugin settings", keys)
        changes = file_changes(files_before, files_after)
        backups = [p for p in changes["added"] if BACKUP.match(p)]
        rests = run.json(RAW_REST, json.dumps(backups))
        provenance = {p: rests[p] == rests["config.yaml"] for p in backups}
        bad = unexpected_changes(changes, files_after, provenance)
        check(bad == [], "Observe changed files beyond config keys and host-owned backups/logs/locks", {"bad": bad, "changes": changes,
                                                                                                    "provenance": provenance})
        return {"mode": mode, "reasons": reasons, "status": items[0], "explain": items[1], "config": items[2:5],
                "settings_changed": keys, "file_changes": changes, "backup_provenance": provenance,
                "host_side_effects": [p for p in changes["added"] + changes["changed"] if p != "config.yaml"]}
    run.step("observe-unknown-readings-without-outside-writes", observe)

    def invalid_external_value():
        run.hermes("config", "set", f"plugins.entries.{PLUGIN}.settings.limits.week_block_pct", "250")
        status = single(run.probe("status"))
        invalid = status["settings_invalid"].get("limits.week_block_pct") or {}
        check(set(invalid) == {"saved_type", "reason"} and status["decision_incomplete"], "invalid value not reported by type", status)
        check("250" not in json.dumps(invalid), "invalid value echoed", invalid)
        refused = single(run.probe("config set limits.week_block_pct 250"))
        check(not refused["ok"], "command accepted an invalid value", refused)
        single(run.probe("config reset limits.week_block_pct"))
        check(single(run.probe("status"))["settings_invalid"] == {}, "reset did not clear the invalid value")
        return {"status_invalid": invalid, "refused": refused.get("error")}
    run.step("external-invalid-value-reported-and-reset", invalid_external_value)

    def unenrolled_profile():
        before, files_before = run.config(), files()
        created = run.hermes("profile", "create", NEW_PROFILE, check=False)
        listed = run.hermes("-p", NEW_PROFILE, "plugins", "list", "--plain", "--no-bundled", check=False)
        home = f"{STATE}/profiles/{NEW_PROFILE}"
        other = json.loads(run.docker("exec", "-i", "-e", f"HERMES_HOME={home}", TARGET, PY, "-I", "-B", "-c", CONFIG).stdout.strip().splitlines()[-1])
        plugin_tree = run.exec("test", "-e", f"{home}/plugins/{PLUGIN}", check=False).returncode == 0
        after, files_after = run.config(), files()
        check(created.returncode == 0, "profile creation failed", created.stdout + created.stderr)
        check(other["entry"] is None and not plugin_tree and PLUGIN not in (other["enabled"] or []), "new profile is enrolled", other)
        check(after == before, "creating a profile changed the enrolled profile's configuration", {"before": before, "after": after})
        status = single(run.probe("status"))
        check(status["mode_effective"] == "observe", "enrolled profile lost Observe", status)
        return {"list": listed.stdout[-1500:], "new_profile_config": other, "plugin_tree": plugin_tree,
                "file_changes": file_changes(files_before, files_after)}
    run.step("new-profile-not-enrolled", unenrolled_profile)

    def rollback_revision():
        neutral()
        installed = install(rollback, force=True)
        smoke = enable_and_smoke(rollback)
        return {"install": installed, "smoke": smoke}
    run.step("rollback-to-previous-public-revision", rollback_revision)

    def roll_forward():
        neutral()
        installed = install(candidate, force=True)
        smoke = enable_and_smoke(candidate)
        observed = single(run.probe("mode observe"))
        observe_contract(single(run.probe("status")), 2)
        return {"install": installed, "smoke": smoke, "observe": observed}
    run.step("return-to-candidate-and-observe", roll_forward)

    def remove_and_reinstall():
        neutral()
        before = run.config()
        run.hermes("plugins", "remove", PLUGIN)
        after = run.config()
        gone = run.exec("test", "!", "-e", f"{STATE}/plugins/{PLUGIN}", check=False).returncode == 0
        result = run.probe("status")
        check(gone and not result["handler"] and after["entry"] is None, "removal left the plugin", {"gone": gone, "after": after})
        check(after["rest_sha256"] == before["rest_sha256"], "removal changed configuration outside the plugin entry", {"before": before, "after": after})
        installed = install(candidate, force=False)
        smoke = enable_and_smoke(candidate)
        check(smoke["settings_invalid"] == {} and smoke["settings"]["roles"] == {}, "reinstall did not start from defaults", smoke)
        return {"removed": {"before": before, "after": after}, "install": installed, "smoke": smoke}
    run.step("off-remove-and-reinstall", remove_and_reinstall)

    run.step("isolation-negative-and-positive-controls", lambda: isolation(run, production))

    def final():
        tree = run.tree(candidate, GITHUB)
        status = single(run.probe("status"))
        check(status["mode_effective"] == "off" and status["deployment"]["revision"] == candidate, "final state not candidate OFF", status)
        host_after = host_state(production)
        check(host_after == host_before, "production Hermes state changed during the run", {"before": host_before, "after": host_after})
        return {"tree": tree, "status": status, "host": host_after}
    run.step("final-state-and-production-unchanged", final)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Failure as exc:
        raise SystemExit(str(exc))
