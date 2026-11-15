"""Selection is a declaration, not proof of installation or isolation."""
import json
import unittest
from test_default import Context, load_entry


class IdentityTests(unittest.TestCase):
    def test_explicit_candidate_selection_is_frozen_until_reload(self):
        ctx = Context()
        selected = {
            "schema": 1, "environment": "test", "channel": "candidate",
            "revision": "a" * 40, "origin": "gcunharodrigues/hermes-quota-router",
        }
        ctx.settings["deployment"] = dict(selected)
        load_entry().register(ctx)
        command = ctx.commands["quota-router"]
        status = json.loads(command("status --json"))
        self.assertEqual(status.get("deployment"), selected)
        self.assertEqual(status["identity_evidence"], "declared_not_verified")
        self.assertFalse(status["installed_verified"])
        self.assertEqual(status["compatibility"]["auto"], "unavailable")
        self.assertIn("python", status["compatibility"])
        ctx.settings["deployment"]["revision"] = "b" * 40
        status = json.loads(command("status --json"))
        self.assertEqual(status["deployment"], selected)
        self.assertTrue(status["restart_required"])
        self.assertEqual(status["deployment_saved"]["revision"], "b" * 40)
        self.assertEqual(ctx.writes, [])
        for field, bad in (("revision", "main"), ("revision", "A" * 39),
                           ("environment", "production"), ("channel", "stable"),
                           ("schema", True), ("origin", "https://host.invalid/repo")):
            with self.subTest(field=field, bad=bad):
                ctx.settings["deployment"] = dict(selected, **{field: bad})
                load_entry().register(ctx)
                status = json.loads(ctx.commands["quota-router"]("status --json"))
                self.assertEqual(status["identity_evidence"], "invalid")
                self.assertIsNone(status["deployment"])
                self.assertFalse(status["installed_verified"])
        ctx.settings.pop("deployment")
        load_entry().register(ctx)
        status = json.loads(ctx.commands["quota-router"]("status --json"))
        self.assertEqual(status["identity_evidence"], "unknown")
        self.assertIsNone(status["deployment"])


if __name__ == "__main__":
    unittest.main()
