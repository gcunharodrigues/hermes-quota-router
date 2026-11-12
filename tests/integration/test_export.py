"""Synthetic exported payload, not a Hermes installation or isolation proof."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from quota_router.line_gate import check_lines
from quota_router.verification import hash_tree, verify_tree

ROOT = Path(__file__).resolve().parents[2]


class ExportTests(unittest.TestCase):
    def test_candidate_exports_and_reloads_saved_observe_without_extra_capabilities(self):
        self.assertTrue((ROOT / "plugin.yaml").is_file(), "Native manifest missing")
        manifest = json.loads((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "standalone")
        self.assertEqual(manifest["manifest_version"], 2)
        self.assertEqual(manifest["python_dependencies"], [])
        self.assertEqual(manifest["provides_hooks"], [])
        names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
        names = sorted(set(filter(None, names)) | {"plugin.yaml"})
        self.assertEqual(check_lines(ROOT, names), [])
        with tempfile.TemporaryDirectory(prefix="hqr-export-") as directory:
            base = Path(directory)
            target = base / "candidate"
            target.mkdir()
            for name in names:
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / name).read_bytes())
            hashes = hash_tree(target, names)
            self.assertEqual(verify_tree(target, hashes), [])
            self.assertEqual(set(hashes), set(names))
            state = base / "synthetic-settings.json"
            state.write_text("{}", encoding="utf-8")

            class Context:
                def get_config(self, key, default=None):
                    return json.loads(state.read_text(encoding="utf-8")).get(key, default)

                def set_config(self, key, value):
                    data = json.loads(state.read_text(encoding="utf-8"))
                    data[key] = value
                    state.write_text(json.dumps(data), encoding="utf-8")

                def register_command(self, name, handler, **kwargs):
                    self.command = handler
                    return object()

                def on_unload(self, callback):
                    self.unload = callback
                    return object()

                def __getattr__(self, name):
                    raise AssertionError(f"Unexpected host capability: {name}")

            for index, requested in enumerate(("mode observe", "status", "mode off")):
                module_name = f"hqr_export_{index}"
                spec = importlib.util.spec_from_file_location(module_name, target / "__init__.py",
                                                              submodule_search_locations=[str(target)])
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                try:
                    spec.loader.exec_module(module)
                    ctx = Context()
                    module.register(ctx)
                    result = json.loads(ctx.command(requested))
                    self.assertEqual(result["version"], manifest["version"])
                    self.assertEqual(result["mode_effective"], "off" if index == 2 else "observe")
                    self.assertEqual(result["quota_queries"], 0)
                    self.assertEqual(result["extra_inferences"], 0)
                    self.assertFalse(result["auto_available"])
                    ctx.unload()
                finally:
                    for key in list(sys.modules):
                        if key == module_name or key.startswith(module_name + "."):
                            del sys.modules[key]
            self.assertEqual(verify_tree(target, hashes), [])


if __name__ == "__main__":
    unittest.main()
