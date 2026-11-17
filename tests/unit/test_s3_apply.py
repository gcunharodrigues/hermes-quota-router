"""S3 closed projections, recovery and baseline over disposable synthetic configuration."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from s3_fakes import Backend, CONFIG, TARGET, qualified


class ApplyTests(unittest.TestCase):
    def engine(self, root, backend=None, **kwargs):
        self.assertIsNotNone(importlib.util.find_spec("quota_router.apply"), "S3 apply engine is missing")
        from quota_router.apply import Engine
        return Engine(root, backend or Backend(), compatible=qualified, **kwargs)

    def test_closed_projection_preserves_other_options_and_off_restores_absence(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            before = copy.deepcopy(backend.document)
            engine = self.engine(root, backend)
            engine.cycle({"conversation": TARGET, "general": TARGET}, now=100)
            self.assertEqual(backend.document["model"]["provider"], "anthropic")
            options = backend.document["delegation"]["backends"]["model_map"]["options"]
            self.assertEqual(options[1], before["delegation"]["backends"]["model_map"]["options"][1])
            self.assertEqual(options[0]["fallbacks"], ["synthetic"])
            self.assertEqual(backend.document["model"]["base_url"], "https://api.anthropic.com")
            self.assertEqual(backend.document["model"]["api_mode"], "anthropic_messages")
            engine.restore(now=200)
            self.assertEqual(backend.document, before)
            self.assertFalse((Path(root) / "journal.json").exists())

    def test_divergence_excludes_entire_group_in_apply_and_off(self):
        for restoring in (False, True):
            with self.subTest(restoring=restoring), tempfile.TemporaryDirectory() as root:
                backend = Backend()
                engine = self.engine(root, backend)
                engine.cycle({"conversation": TARGET}, now=100)
                backend.document["model"]["default"] = "gpt-6.1-terra"
                before, count = copy.deepcopy(backend.document), len(backend.writes)
                (engine.restore(now=200) if restoring else engine.cycle({"conversation": TARGET}, now=200))
                self.assertEqual(backend.document, before)
                self.assertEqual(len(backend.writes), count)
                self.assertIn("model.default", engine.report(201)["groups_out"]["conversation"])

    def test_four_recovery_cases_and_repeated_baseline(self):
        for case in ("prior", "target", "mixture", "third"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as root:
                backend = Backend()
                engine = self.engine(root, backend)
                engine.cycle({"conversation": TARGET}, now=100)
                state = json.loads((Path(root) / "state.json").read_text())
                prior = state["groups"]["conversation"]["baseline"]
                target = state["groups"]["conversation"]["last"]
                from quota_router.apply import durable
                durable(Path(root) / "journal.json", {"group": "conversation", "prior": prior, "target": target,
                                                      "at": 200, "restore": False})
                if case in ("prior", "mixture"):
                    backend.document = copy.deepcopy(CONFIG)
                if case == "mixture":
                    backend.document["model"]["provider"] = "anthropic"
                if case == "third":
                    backend.document["model"]["provider"] = "custom"
                before, count = copy.deepcopy(backend.document), len(backend.writes)
                recovered = self.engine(root, backend)
                recovered.recover()
                if case in ("prior", "third"):
                    self.assertEqual(backend.document, before)
                    self.assertEqual(len(backend.writes), count)
                else:
                    self.assertEqual(backend.document["model"]["provider"], "anthropic")
                    self.assertEqual(backend.document["model"]["default"], TARGET["model"])
                if case == "third":
                    self.assertIn("conversation", recovered.report(201)["groups_out"])
                else:
                    self.assertFalse((Path(root) / "journal.json").exists())
                self.assertEqual(json.loads((Path(root) / "state.json").read_text())["groups"]["conversation"]["baseline"], prior)

    def test_secret_preconditions_at_enrollment_and_before_every_write(self):
        for key in ("api_key", "api", "key_env", "api_key_env", "context_length", "model", "name"):
            for later in (False, True):
                with self.subTest(key=key, later=later), tempfile.TemporaryDirectory() as root:
                    backend = Backend()
                    engine = self.engine(root, backend)
                    if later:
                        engine.cycle({"conversation": TARGET}, now=100)
                    secret = "SYNTHETIC_PRIVATE_VALUE_DO_NOT_PERSIST"
                    backend.document["model"][key] = secret
                    before, count = copy.deepcopy(backend.document), len(backend.writes)
                    engine.cycle({"conversation": TARGET}, now=200)
                    engine.restore(now=300)
                    self.assertEqual(backend.document, before)
                    self.assertEqual(len(backend.writes), count)
                    self.assertIn("model." + key, engine.report(301)["groups_out"]["conversation"])
                    text = repr(engine.report(301)) + ''.join(p.read_text() for p in Path(root).glob('*.json'))
                    self.assertNotIn(secret, text)

    def test_preconditions_rechecked_for_pending_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            def crash(point):
                if point == "journal":
                    raise RuntimeError("synthetic crash")
            engine = self.engine(root, backend, checkpoint=crash)
            with self.assertRaises(RuntimeError):
                engine.cycle({"conversation": TARGET}, now=100)
            backend.document["model"]["api"] = "SYNTHETIC_PRIVATE_VALUE"
            count = len(backend.writes)
            recovered = self.engine(root, backend)
            recovered.recover()
            self.assertEqual(len(backend.writes), count)
            self.assertIn("model.api", recovered.report(200)["groups_out"]["conversation"])
            self.assertNotIn("SYNTHETIC_PRIVATE_VALUE", repr(recovered.report(200)))

    def test_consumer_disable_restores_and_new_enrollment_gets_new_baseline(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            engine = self.engine(root, backend)
            engine.cycle({"conversation": TARGET, "general": TARGET}, now=100)
            engine.cycle({"general": TARGET}, enabled={"general"}, now=200)
            self.assertEqual(backend.document["model"], CONFIG["model"])
            backend.document["model"]["default"] = "gpt-6.1-terra"
            engine.cycle({"conversation": TARGET}, now=300)
            engine.restore(now=400)
            self.assertEqual(backend.document["model"]["default"], "gpt-6.1-terra")

    def test_fallback_edit_is_not_divergence_and_route_credentials_exclude(self):
        for field in (None, "api_key", "api", "key_env", "api_key_env", "base_url"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                backend = Backend()
                engine = self.engine(root, backend)
                engine.cycle({"general": TARGET}, now=100)
                route = backend.document["delegation"]["backends"]["model_map"]["options"][0]
                route["fallbacks"] = ["edited"]
                if field:
                    route[field] = "SYNTHETIC_PRIVATE_VALUE"
                before = copy.deepcopy(backend.document)
                engine.restore(now=200)
                if field:
                    self.assertEqual(backend.document, before)
                    self.assertIn("general", engine.report(201)["groups_out"])
                else:
                    reread = backend.read()["delegation"]["backends"]["model_map"]["options"][0]
                    self.assertEqual(reread["fallbacks"], ["edited"])
                    self.assertEqual(backend.document["delegation"]["backends"]["model_map"]["options"][0]["provider"], "openai-codex")

    def test_compatibility_failure_has_zero_writes_including_recovery_and_restore(self):
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            engine = self.engine(root, backend)
            engine.cycle({"conversation": TARGET}, now=100)
            engine.compatible = lambda: {"ok": False, "reasons": ["host.function"]}
            before, count = copy.deepcopy(backend.document), len(backend.writes)
            engine.cycle({"conversation": dict(TARGET, provider="openai-codex", model="gpt-6.1-sol")}, now=200)
            engine.restore(now=300)
            self.assertEqual(backend.document, before)
            self.assertEqual(len(backend.writes), count)
            self.assertEqual(engine.report(301)["compatibility"]["reasons"], ["host.function"])


if __name__ == "__main__":
    unittest.main()
