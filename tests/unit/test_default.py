"""Synthetic command boundary; no host, network, data or credentials are loaded."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Context:
    def __init__(self):
        self.settings = {}
        self.commands = {}
        self.cleanup = []
        self.writes = []

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def set_config(self, key, value):
        self.writes.append(key)
        self.settings[key] = value

    def register_command(self, name, handler, **kwargs):
        self.commands[name] = handler
        return object()

    def on_unload(self, callback):
        self.cleanup.append(callback)
        return object()

    def __getattr__(self, name):
        raise AssertionError(f"Unexpected host capability: {name}")


def load_entry():
    path = ROOT / "__init__.py"
    if not path.is_file():
        raise AssertionError("Plugin entry missing")
    spec = importlib.util.spec_from_file_location("hqr_synthetic", path, submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DefaultTests(unittest.TestCase):
    def test_register_exposes_off_management_without_host_effects(self):
        ctx = Context()
        load_entry().register(ctx)
        self.assertEqual(set(ctx.commands), {"quota-router"})
        status = json.loads(ctx.commands["quota-router"]("status --json"))
        self.assertEqual(status["mode_saved"], "off")
        self.assertEqual(status["mode_effective"], "off")
        self.assertEqual(status["quota"], {"state": "unknown", "source": None})
        self.assertEqual(status["extra_inferences"], 0)
        self.assertEqual(status["quota_queries"], 0)
        self.assertFalse(status["auto_available"])
        self.assertEqual(ctx.writes, [])
        self.assertEqual(len(ctx.cleanup), 1)


if __name__ == "__main__":
    unittest.main()
