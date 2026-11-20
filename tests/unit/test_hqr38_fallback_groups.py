"""HQR-38 safety net groups: closed `fallback_providers` projections (decisions/hqr-38-spec.md, D-28/D-29).

Native entry shape: `hermes_cli/fallback_config.py` (`provider`, `model`, optional `base_url`/`api_mode`); credentials never pass.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from s3_fakes import Backend, TARGET, qualified
from quota_router import groups
from quota_router.apply import Engine

OPTIONS = "delegation.backends.model_map.options"
OPUS = {"provider": "anthropic", "model": "claude-opus-5-5"}
SOL = {"provider": "openai-codex", "model": "gpt-6.1-sol"}


def tree(root):
    return {path.name: path.read_text() for path in Path(root).iterdir() if path.is_file()}


class ProjectionTests(unittest.TestCase):
    def test_group_names_and_absent_projection(self):
        self.assertEqual(groups.fallback_group("conversation"), "fallback:conversation")
        self.assertEqual(groups.fallback_group("general"), "fallback:general")
        self.assertTrue(groups.is_fallback("fallback:general"))
        self.assertFalse(groups.is_fallback("general"))
        document = Backend().read()
        for role in ("conversation", "general"):
            self.assertEqual(groups.project(document, groups.fallback_group(role)), {"fallback_providers": {"present": False}})

    def test_target_writes_the_chain_and_an_empty_chain_only_over_a_present_baseline(self):
        name = groups.fallback_group("general")
        self.assertEqual(groups.target(name, {"chain": [OPUS]}), {"fallback_providers": {"present": True, "value": [OPUS]}})
        absent = {"fallback_providers": {"present": False}}
        present = {"fallback_providers": {"present": True, "value": [SOL]}}
        self.assertEqual(groups.target(name, {"chain": []}, baseline=absent), absent)
        self.assertEqual(groups.target(name, {"chain": []}, baseline=present), {"fallback_providers": {"present": True, "value": []}})

    def test_closed_projection_rejects_credentials_foreign_providers_and_unknown_fields(self):
        name = groups.fallback_group("conversation")
        bad = ([dict(OPUS, api_key="sk-synthetic-secret")], [dict(OPUS, key_env="SYNTHETIC_ENV")],
               [{"provider": "openrouter", "model": "claude-opus-5-5"}], [{"provider": "anthropic", "model": "gpt-6.1-sol"}],
               [dict(OPUS, reasoning_effort="high")], [dict(OPUS, base_url="https://synthetic.invalid")], "text", [OPUS, "x"])
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    groups.validate_projection(name, {"fallback_providers": {"present": True, "value": value}})
        native = dict(OPUS, base_url="https://api.anthropic.com", api_mode="anthropic_messages")
        for value in ([], [OPUS], [native, SOL]):
            projection = {"fallback_providers": {"present": True, "value": value}}
            self.assertEqual(groups.validate_projection(name, projection), projection)

    def test_preconditions_name_only_the_field(self):
        document = Backend().read()
        document["fallback_providers"] = [dict(OPUS, api_key="sk-synthetic-secret")]
        option = document["delegation"]["backends"]["model_map"]["options"][0]
        option["fallback_providers"] = [dict(SOL, key_env="SYNTHETIC_ENV")]
        root = groups.preconditions(document, groups.fallback_group("conversation"))
        route = groups.preconditions(document, groups.fallback_group("general"))
        self.assertEqual(root, ["fallback_providers"])
        self.assertEqual(route, [OPTIONS + ".fallback_providers"])
        self.assertNotIn("synthetic", json.dumps([root, route]).lower())


class EngineTests(unittest.TestCase):
    def selections(self, chain=(OPUS,)):
        return {"conversation": TARGET, "general": TARGET,
                "fallback:conversation": {"chain": list(chain)}, "fallback:general": {"chain": list(chain)}}

    def test_apply_readback_and_off_restore_absent_keys_exactly(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            baseline = backend.read()
            engine = Engine(root, backend, qualified)
            engine.cycle(self.selections(), now=10)
            document = backend.read()
            self.assertEqual(document["fallback_providers"], [OPUS])
            self.assertEqual(document["delegation"]["backends"]["model_map"]["options"][0]["fallback_providers"], [OPUS])
            self.assertEqual(document["delegation"]["backends"]["model_map"]["options"][1], baseline["delegation"]["backends"]["model_map"]["options"][1])
            report = engine.report(10)
            self.assertEqual(report["groups_out"], {})
            for name in ("fallback:conversation", "fallback:general"):
                self.assertTrue(report["safety_net"][name]["active"])
                self.assertEqual(report["safety_net"][name]["values"], groups.project(document, name))
            self.assertTrue(Engine(root, backend, qualified).restore(20))
            self.assertEqual(backend.read(), baseline)
            self.assertNotIn("fallback_providers", backend.read())

    def test_off_restores_a_present_baseline_value(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            backend.document["fallback_providers"] = [dict(OPUS, model="claude-sonnet-5-5")]
            baseline = backend.read()
            engine = Engine(root, backend, qualified)
            engine.cycle(self.selections(), now=5)
            self.assertEqual(backend.read()["fallback_providers"], [OPUS])
            engine.cycle(self.selections(chain=()), now=10)
            self.assertEqual(backend.read()["fallback_providers"], [])
            self.assertNotIn("fallback_providers", backend.read()["delegation"]["backends"]["model_map"]["options"][0])
            self.assertTrue(engine.restore(20))
            self.assertEqual(backend.read(), baseline)

    def test_external_edit_excludes_only_the_safety_net_group(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            baseline = backend.read()
            engine = Engine(root, backend, qualified)
            engine.cycle(self.selections(), now=10)
            backend.document["fallback_providers"] = [dict(SOL, model="gpt-6.1-terra")]
            edited = copy.deepcopy(backend.document["fallback_providers"])
            engine.cycle(self.selections(), now=20)
            report = engine.report(20)
            self.assertEqual(report["groups_out"], {"fallback:conversation": ["fallback_providers"]})
            self.assertEqual(backend.read()["fallback_providers"], edited)
            self.assertTrue(report["groups"]["conversation"]["active"])
            self.assertTrue(engine.restore(30))
            final = backend.read()
            self.assertEqual(final["fallback_providers"], edited)
            self.assertEqual(groups.project(final, "conversation"), groups.project(baseline, "conversation"))
            self.assertEqual(final["delegation"], baseline["delegation"])

    def test_credential_in_baseline_excludes_without_retaining_the_secret(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            backend.document["fallback_providers"] = [dict(OPUS, api_key="sk-synthetic-secret")]
            before = backend.read()
            engine = Engine(root, backend, qualified)
            engine.cycle(self.selections(), now=10)
            self.assertEqual(backend.read()["fallback_providers"], before["fallback_providers"])
            self.assertEqual(engine.report(10)["groups_out"]["fallback:conversation"], ["fallback_providers"])
            self.assertNotIn("sk-synthetic-secret", json.dumps(tree(root)))
            self.assertNotIn("sk-synthetic-secret", json.dumps(engine.report(10)))

    def test_safety_net_group_survives_the_subagent_dependency_rule_for_the_conversation(self):
        def degraded():
            return {"ok": True, "host": "synthetic", "reasons": [], "subagents": {"ok": False}}
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            engine = Engine(root, backend, degraded)
            engine.cycle(self.selections(), now=10)
            self.assertEqual(backend.read()["fallback_providers"], [OPUS])
            self.assertIn("fallback:general", engine.report(10)["groups_out"])


if __name__ == "__main__":
    unittest.main()
