"""Unit tests for the installed lifecycle harness; synthetic inputs only, no Docker or Hermes."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hqr_lifecycle", ROOT / "tests/installed/lifecycle.py")
assert SPEC is not None and SPEC.loader is not None
lifecycle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lifecycle)


def fake_home(base):
    home = base / "hermes-home"
    agent = home / "hermes-agent"
    (agent / ".git" / "refs" / "heads").mkdir(parents=True)
    (agent / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (agent / ".git" / "refs" / "heads" / "main").write_text("a" * 40 + "\n")
    (agent / "uv.lock").write_text("lock")
    (home / "config.yaml").write_text("model: synthetic\n")
    (home / "plugins").mkdir()
    (home / "plugins" / ".install-metadata.json").write_text("{}")
    install = home / "installs" / "abc"
    (install / "environments" / "gen1").mkdir(parents=True)
    (install / "facts.json").write_text("{}")
    return home


class HostStateTests(unittest.TestCase):
    def test_observes_production_without_starting_any_process(self):
        with tempfile.TemporaryDirectory() as directory:
            home = fake_home(Path(directory))
            with mock.patch.object(subprocess, "Popen", side_effect=AssertionError("process started")):
                first = lifecycle.host_state(home)
                (home / "config.yaml").write_text("model: changed\n")
                second = lifecycle.host_state(home)
                (home / "installs" / "abc" / "environments" / "gen2").mkdir()
                third = lifecycle.host_state(home)
        self.assertEqual(first["head"], "a" * 40)
        self.assertNotEqual(first["config_sha256"], second["config_sha256"])
        self.assertNotEqual(second["installs"], third["installs"])

    def test_missing_observation_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            home = fake_home(Path(directory))
            (home / "hermes-agent" / "uv.lock").unlink()
            with self.assertRaises(lifecycle.Failure):
                lifecycle.host_state(home)


class ListenerTests(unittest.TestCase):
    def test_reports_every_non_loopback_listener(self):
        lines = [
            "LISTEN 0 4096 127.0.0.1:22 0.0.0.0:*",
            "LISTEN 0 4096 [::1]:5901 [::]:*",
            "UNCONN 0 0 127.0.0.53%lo:53 0.0.0.0:*",
            "LISTEN 0 10 0.0.0.0:8080 0.0.0.0:*",
            "LISTEN 0 10 *:9000 *:*",
            "LISTEN 0 10 [::]:7000 [::]:*",
            "LISTEN 0 10 10.0.0.5:80 0.0.0.0:*",
            "",
        ]
        self.assertEqual(lifecycle.non_loopback(lines), ["0.0.0.0:8080", "*:9000", "[::]:7000", "10.0.0.5:80"])


    def test_only_the_dhcp_client_is_an_allowed_udp_exception(self):
        tcp = ["LISTEN 0 10 127.0.0.1:22 0.0.0.0:*", "LISTEN 0 10 10.0.0.5:68 0.0.0.0:*"]
        udp = [
            "UNCONN 0 0 10.0.0.5%eth0:68 0.0.0.0:*",
            "UNCONN 0 0 0.0.0.0:5353 0.0.0.0:*",
            "UNCONN 0 0 0.0.0.0:68 0.0.0.0:*",
            "UNCONN 0 0 *:68 *:*",
            "UNCONN 0 0 10.0.0.5:68 0.0.0.0:*",
        ]
        self.assertEqual(
            lifecycle.unexpected_listeners(tcp, udp),
            ["10.0.0.5:68", "0.0.0.0:5353", "0.0.0.0:68", "*:68", "10.0.0.5:68"],
        )


class ScanTests(unittest.TestCase):
    def test_only_a_safe_verdict_allows_install(self):
        lifecycle.require_safe_scan({"verdict": "safe", "findings": 0})
        for verdict in ("caution", "dangerous", None):
            with self.assertRaises(lifecycle.Failure):
                lifecycle.require_safe_scan({"verdict": verdict, "findings": 1})


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"HQR_DOCKER_CLIENT": "/nonexistent"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_refuses_a_used_receipt_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "01-old.json").write_text("{}")
            with self.assertRaises(lifecycle.Failure):
                lifecycle.Run(directory)

    def test_operational_exception_writes_a_failed_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            run = lifecycle.Run(Path(directory) / "receipts")

            def broken():
                raise RuntimeError("synthetic timeout")

            with self.assertRaises(SystemExit) as stopped:
                run.step("broken", broken)
            receipt = json.loads((Path(directory) / "receipts" / "01-broken.json").read_text())
        self.assertEqual(stopped.exception.code, 1)
        self.assertFalse(receipt["pass"])
        self.assertIn("RuntimeError", receipt["failure"])


if __name__ == "__main__":
    unittest.main()
