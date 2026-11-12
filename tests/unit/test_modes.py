"""Synthetic lifecycle transitions through the native-shaped command handler."""
import json
import unittest
from test_default import Context, load_entry


class ModeTests(unittest.TestCase):
    def test_observe_off_auto_rejection_reload_and_unload(self):
        ctx = Context()
        load_entry().register(ctx)
        command = ctx.commands["quota-router"]
        observed = json.loads(command("mode observe"))
        self.assertEqual(observed["mode_saved"], "observe")
        self.assertEqual(observed["mode_effective"], "observe")
        self.assertEqual(ctx.settings, {"mode": "observe"})
        before = dict(ctx.settings)
        refused = json.loads(command("mode auto"))
        self.assertFalse(refused["ok"])
        self.assertEqual(ctx.settings, before)
        for invalid in ("mode observe extra", "mode ON", "wat", "status extra"):
            self.assertFalse(json.loads(command(invalid))["ok"])
            self.assertEqual(ctx.settings, before)
        load_entry().register(ctx)
        command = ctx.commands["quota-router"]
        self.assertEqual(json.loads(command("status"))["mode_effective"], "observe")
        ctx.settings["mode"] = "off"
        pending = json.loads(command("status"))
        self.assertTrue(pending["restart_required"])
        self.assertEqual(pending["mode_effective"], "observe")
        self.assertEqual(pending["mode_saved"], "off")
        off = json.loads(command("mode off"))
        self.assertEqual(off["mode_effective"], "off")
        self.assertFalse(off["restart_required"])
        self.assertEqual(off["draining"], "not_applicable_no_admission_in_S1")
        for _ in range(5):
            result = json.loads(command("explain"))
            self.assertEqual(result["quota_queries"], 0)
            self.assertEqual(result["extra_inferences"], 0)
            self.assertEqual(result["quota"]["state"], "unknown")
        ctx.cleanup[-1]()
        self.assertFalse(json.loads(command("mode observe"))["ok"])
        self.assertEqual(ctx.settings["mode"], "off")
        self.assertEqual(json.loads(command("status"))["mode_effective"], "unloaded")


if __name__ == "__main__":
    unittest.main()
