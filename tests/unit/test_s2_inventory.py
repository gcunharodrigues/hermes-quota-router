"""S2 inventory and equivalence map (scenarios B1, B4, B5, B7, C8, C9 and C11)."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from s2_fakes import NOW, claude, codex, settings
import sys
import types
from unittest import mock

from quota_router.inventory import native_sources, read, read_jobs_file
from quota_router.mapping import propose
from quota_router.readings import normalize

def fake_host(path, document):
    """Stand-in host modules: `read_config_doc` returns or raises `document`; any other loader fails the test."""
    def read_config_doc(config_path):
        assert Path(config_path) == path
        if isinstance(document, Exception):
            raise document
        return document

    def forbidden(*_args, **_kwargs):
        raise AssertionError("mutating native loader called")

    config = types.ModuleType("hermes_cli.config")
    config.get_config_path = lambda: path
    config.read_raw_config = config.load_config_readonly = config.load_config = forbidden
    backend = types.ModuleType("hermes_cli.config_backend")
    backend.read_config_doc = read_config_doc
    return {"hermes_cli": types.ModuleType("hermes_cli"), "hermes_cli.config": config, "hermes_cli.config_backend": backend}


CONFIG = {
    "model": {"provider": "openai-codex", "default": "gpt-6.1-sol", "base_url": "https://example.invalid", "api_mode": "codex_responses"},
    "delegation": {
        "provider": "openai-codex", "model": "gpt-6.1-terra", "reasoning_effort": "medium",
        "backends": {"model_map": {"default": "general", "options": [
            {"name": "general", "description": "d", "provider": "openai-codex", "model": "gpt-6.1-terra", "reasoning_effort": "medium"},
            {"name": "deep", "description": "d", "provider": "openai-codex", "model": "gpt-6.1-sol", "reasoning_effort": "xhigh"},
        ]}},
    },
    "agent": {"reasoning_effort": "xhigh"},
}
JOBS = [
    {"id": "a", "name": "unpinned"},
    {"id": "b", "name": "full pin", "provider": "openai-codex", "model": "gpt-6.1-sol", "base_url": "https://example.invalid"},
    {"id": "c", "name": "model only", "model": "gpt-6.1-terra"},
    {"id": "d1e2", "name": "send report to user@example.com with token sk-123", "base_url": "https://example.invalid"},
]


class InventoryTests(unittest.TestCase):
    def test_reads_routes_conversation_and_cron_pins(self):
        inventory = read(CONFIG, JOBS)
        self.assertEqual(inventory["conversation"], {"provider": "openai-codex", "model": "gpt-6.1-sol", "effort": "xhigh"})
        self.assertEqual([r["name"] for r in inventory["routes"]], ["general", "deep"])
        self.assertEqual(inventory["cron"]["unpinned"], 1)
        self.assertEqual(inventory["cron"]["pinned"], 1)
        self.assertEqual(inventory["cron"]["partial_pins"], [{"job": "c", "missing": ["provider"]},
                                                             {"job": "d1e2", "missing": ["provider", "model"]}])
        self.assertNotIn("user@example.com", repr(inventory))
        self.assertNotIn("sk-123", repr(inventory))
        self.assertFalse(inventory["cron"]["globals_writable"])
        self.assertIn("auxiliary", inventory["not_governed"])
        self.assertNotIn("example.invalid", repr(inventory))

    def test_unavailable_sources(self):
        inventory = read(None, None)
        self.assertEqual(inventory["state"], "unavailable")

    def test_untrusted_strings_are_replaced(self):
        config = json.loads(json.dumps(CONFIG))
        config["delegation"]["backends"]["model_map"]["options"].append(
            {"name": "bad name with spaces and user@example.com", "provider": "openai-codex", "model": "x y"})
        inventory = read(config, [{"id": "../../etc", "model": "m"}])
        self.assertEqual(inventory["routes"][-1]["name"], "invalid-3")
        self.assertIsNone(inventory["routes"][-1]["model"])
        self.assertEqual(inventory["cron"]["partial_pins"][0]["job"], "job-1")
        self.assertNotIn("example.com", repr(inventory))

    def test_native_config_is_read_from_the_raw_document_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            for document, expected in ((FileNotFoundError(), {}), (ValueError("bad yaml"), None), ({"model": {}}, {"model": {}}),
                                       (["not", "a", "mapping"], None)):
                with mock.patch.dict(sys.modules, fake_host(path, document)):
                    config, jobs = native_sources()
                self.assertEqual(config, expected, document)
                self.assertEqual(jobs, [])

    def test_native_efforts_are_kept(self):
        config = json.loads(json.dumps(CONFIG))
        options = config["delegation"]["backends"]["model_map"]["options"]
        options.append({"name": "maxed", "provider": "openai-codex", "model": "gpt-6.1-sol", "reasoning_effort": "max"})
        options.append({"name": "ultra", "provider": "openai-codex", "model": "gpt-6.1-sol", "reasoning_effort": "ultra"})
        inventory = read(config, [])
        self.assertEqual([r["effort"] for r in inventory["routes"]][-2:], ["max", "ultra"])
        pair = propose(inventory, {}, settings())["variants"]["base"]["maxed"]
        self.assertEqual(pair["openai-codex"], {"model": "gpt-6.1-sol", "effort": "max"})
        from quota_router.settings import validate
        self.assertTrue(validate("roles", {"maxed": pair})[0])
        options.append({"name": "terra-max", "provider": "openai-codex", "model": "gpt-6.1-terra", "reasoning_effort": "max"})
        strong = propose(read(config, []), {}, settings())["variants"]["base"]["terra-max"]
        self.assertEqual(strong["anthropic"], {"model": "claude-opus-5-5", "effort": "max"})

    def test_secret_shaped_identifiers_are_dropped(self):
        config = json.loads(json.dumps(CONFIG))
        config["delegation"]["provider"] = "sk-abc123"
        config["delegation"]["reasoning_effort"] = "skabcdef"
        jobs = [{"id": "ghp_abcdefghijklmnop", "model": "gpt-6.1-terra"}, {"id": "xoxb-123", "provider": "sk-x"}]
        inventory = read(config, jobs)
        self.assertIsNone(inventory["delegation_default"]["provider"])
        self.assertIsNone(inventory["delegation_default"]["effort"])
        self.assertEqual([p["job"] for p in inventory["cron"]["partial_pins"]], ["job-1", "job-2"])
        for text in ("ghp_", "xoxb", "sk-", "skabc"):
            self.assertNotIn(text, repr(inventory))

    def test_secret_shaped_route_strings_are_dropped(self):
        config = json.loads(json.dumps(CONFIG))
        options = config["delegation"]["backends"]["model_map"]["options"]
        options.append({"name": "sk-proj-abcdef123456", "provider": "openai-codex", "model": "https://example.invalid/private"})
        options.append({"name": "leak", "provider": "anthropic", "model": "sk-ant-api03-abcdef"})
        inventory = read(config, [])
        self.assertEqual([r["name"] for r in inventory["routes"]][-2:], ["invalid-3", "leak"])
        self.assertIsNone(inventory["routes"][-2]["model"])
        self.assertIsNone(inventory["routes"][-1]["model"])
        self.assertNotIn("example.invalid/private", repr(inventory))
        self.assertNotIn("sk-", repr(inventory))

    def test_jobs_file_is_read_without_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobs.json"
            path.write_text(json.dumps([{"id": "legacy-list"}]), encoding="utf-8")
            os.chmod(path, 0o644)
            before = (path.read_bytes(), path.stat().st_mode, path.stat().st_mtime_ns, sorted(os.listdir(directory)))
            self.assertEqual(read_jobs_file(path), [{"id": "legacy-list"}])
            path.write_text(json.dumps({"jobs": [{"id": "wrapped"}]}), encoding="utf-8")
            self.assertEqual(read_jobs_file(path), [{"id": "wrapped"}])
            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(read_jobs_file(path))
            self.assertEqual(read_jobs_file(Path(directory) / "missing.json"), [])
            path.write_text(json.dumps([{"id": "legacy-list"}]), encoding="utf-8")
            os.utime(path, ns=(before[2], before[2]))
            read_jobs_file(path)
            self.assertEqual((path.read_bytes(), path.stat().st_mode, path.stat().st_mtime_ns, sorted(os.listdir(directory))), before)


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.inventory = read(CONFIG, JOBS)

    def r(self, astra):
        return {"openai-codex": normalize("openai-codex", codex(10, astra=astra), NOW, 60),
                "anthropic": normalize("anthropic", claude(10), NOW, 60)}

    def test_four_variants_and_conversation_bound_to_sol_xhigh(self):
        result = propose(self.inventory, self.r(True), settings())
        self.assertEqual(set(result["variants"]), {"base", "fable", "astra", "fable+astra"})
        for variant in result["variants"].values():
            self.assertEqual(variant["conversation"]["openai-codex"], {"model": "gpt-6.1-sol", "effort": "xhigh"})
        self.assertEqual(result["variants"]["astra"]["deep"]["openai-codex"]["model"], "gpt-6-astra")
        self.assertEqual(result["variants"]["fable"]["deep"]["anthropic"]["model"], "claude-fable-5-2")
        self.assertEqual(result["variants"]["base"]["general"]["anthropic"]["model"], "claude-sonnet-5-5")
        self.assertEqual(result["status"], "proposal_not_approved")
        self.assertEqual(result["effective_variant"], "base")

    def test_non_codex_and_inherited_routes_get_provider_specific_pairs(self):
        config = json.loads(json.dumps(CONFIG))
        options = config["delegation"]["backends"]["model_map"]["options"]
        options.append({"name": "claude-side", "provider": "anthropic", "model": "claude-opus-5-5", "reasoning_effort": "xhigh"})
        options.append({"name": "inherits"})
        result = propose(read(config, JOBS), self.r(True), settings())
        claude_side = result["variants"]["base"]["claude-side"]
        self.assertEqual(claude_side["openai-codex"]["model"], "gpt-6.1-sol")
        self.assertEqual(claude_side["anthropic"]["model"], "claude-opus-5-5")
        inherits = result["variants"]["base"]["inherits"]
        self.assertEqual(inherits["openai-codex"], {"model": "gpt-6.1-terra", "effort": "medium"})
        self.assertEqual(inherits["anthropic"]["model"], "claude-sonnet-5-5")

    def test_effective_variant_follows_settings_and_availability(self):
        on = settings({"models.astra": True, "models.fable": True})
        available = propose(self.inventory, self.r(True), on)
        self.assertIn("fable_window_not_visible", available["notes"])
        self.assertEqual(available["effective_variant"], "base")
        self.assertIn("astra_catalog_not_verifiable_by_plugin", available["notes"])
        missing = propose(self.inventory, self.r(False), settings({"models.astra": True}))
        self.assertEqual(missing["effective_variant"], "base")
        self.assertIn("astra_unavailable", missing["notes"])


if __name__ == "__main__":
    unittest.main()
