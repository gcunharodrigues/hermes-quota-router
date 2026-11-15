"""Operational assertions against the explicitly admitted Docker target (internet egress, no host paths)."""
import json
import os
from pathlib import Path
import subprocess
import unittest


class InstalledRuntimeTests(unittest.TestCase):
    def test_whole_runtime_is_separate_without_host_paths(self):
        client = Path(os.environ["HQR_DOCKER_CLIENT"])
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(client / "home"),
            "DOCKER_CONFIG": str(client / "docker"),
            "DOCKER_HOST": "unix:///var/run/docker.sock",
        }
        inspected = subprocess.run(
            ["docker", "inspect", "hqr-s1-test"], env=environment,
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        target = json.loads(inspected.stdout)[0]
        self.assertTrue(target["State"]["Running"])
        # Only the task-created Docker volume holds Hermes state; no host path is mounted.
        self.assertIn(target["HostConfig"]["Binds"], (None, ["hqr-s1-state-net:/home/hqr/state"]))
        self.assertEqual(len(target["Mounts"]), 1, target["Mounts"])
        mount = target["Mounts"][0]
        self.assertEqual(mount["Type"], "volume")
        self.assertEqual(mount["Name"], "hqr-s1-state-net")
        self.assertEqual(mount["Destination"], "/home/hqr/state")
        self.assertEqual(mount["Driver"], "local")
        volume = subprocess.run(
            ["docker", "volume", "inspect", "hqr-s1-state-net"], env=environment,
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(volume.returncode, 0, volume.stderr)
        volume = json.loads(volume.stdout)[0]
        self.assertEqual(volume["Labels"].get("hqr.task"), "t_1c0d7681")
        self.assertFalse(volume["Options"])
        self.assertEqual(target["HostConfig"]["NetworkMode"], "bridge")
        self.assertEqual(sorted(target["NetworkSettings"]["Networks"]), ["bridge"])
        self.assertFalse(target["HostConfig"]["Privileged"])
        self.assertFalse(target["HostConfig"]["CapAdd"])
        self.assertNotEqual(target["HostConfig"]["PidMode"], "host")
        self.assertNotEqual(target["HostConfig"]["IpcMode"], "host")
        self.assertFalse(target["HostConfig"]["PortBindings"])
        self.assertEqual(target["HostConfig"]["Memory"], 0)
        self.assertEqual(target["HostConfig"]["NanoCpus"], 0)
        self.assertEqual(target["Config"]["Labels"]["hqr.task"], "t_1c0d7681")
        probe = subprocess.run(
            ["docker", "exec", "hqr-s1-test", "/opt/hermes-venv/bin/python", "-c",
             "import sys, hermes_cli.plugins; "
             "assert sys.version_info[:3] == (3, 14, 10); "
             "assert sys.prefix == '/opt/hermes-venv'; "
             "assert hermes_cli.plugins.__file__.startswith('/opt/hermes/')"],
            env=environment, text=True, capture_output=True, check=False,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)
