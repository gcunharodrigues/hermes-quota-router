"""Verify installed bytes against the public, immutable Git candidate."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import unittest


class InstalledCandidateTests(unittest.TestCase):
    def test_selected_candidate_bytes_are_installed(self):
        revision = "ad3e180f32adea3c25a2ef91280f1f6308729a47"
        paths = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", revision], text=True,
        ).splitlines()
        expected = {
            path: hashlib.sha256(subprocess.check_output(
                ["git", "show", revision + ":" + path],
            )).hexdigest() for path in paths
        }
        script = '''import hashlib,json,pathlib,subprocess
root=pathlib.Path('/home/hqr/state/plugins/hermes-quota-router')
assert root.is_dir(), 'selected candidate is not installed'
expected=json.loads(MANIFEST)
actual={}
for path in root.rglob('*'):
 relative=path.relative_to(root)
 if relative.parts[0]=='.git': continue
 assert not path.is_symlink(), str(relative)
 if path.is_file(): actual[str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
assert actual==expected, {'missing':sorted(expected.keys()-actual.keys()),'extra':sorted(actual.keys()-expected.keys()),'modified':[p for p in expected.keys() & actual.keys() if expected[p]!=actual[p]]}
assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==REVISION
metadata=json.loads((root.parent/'.install-metadata.json').read_text())[root.name]
assert metadata['revision']==REVISION
assert metadata['pinned'] is True
assert metadata['source']=='https://github.com/gcunharodrigues/hermes-quota-router.git'
print(json.dumps({'revision':REVISION,'files':len(actual),'metadata':metadata},sort_keys=True))
'''.replace("MANIFEST", repr(json.dumps(expected))).replace("REVISION", repr(revision))
        client = Path(os.environ["HQR_DOCKER_CLIENT"])
        environment = {
            "PATH": "/usr/bin:/bin", "HOME": str(client / "home"),
            "DOCKER_CONFIG": str(client / "docker"),
            "DOCKER_HOST": "unix:///var/run/docker.sock",
        }
        probe = subprocess.run(
            ["docker", "exec", "-i", "hqr-s1-test", "/opt/hermes-venv/bin/python", "-"],
            input=script, env=environment, text=True, capture_output=True, check=False,
        )
        self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)
