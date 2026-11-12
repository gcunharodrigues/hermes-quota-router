"""Fail safely without echoing native settings errors or invalid values."""
import json
import unittest
from test_default import Context, load_entry


class FailureTests(unittest.TestCase):
    def test_unreadable_settings_do_not_announce_effective_off(self):
        class Unreadable(Context):
            def get_config(self, key, default=None):
                raise OSError("sensitive native error")

        ctx = Unreadable()
        load_entry().register(ctx)
        result = json.loads(ctx.commands["quota-router"]("status"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["mode_effective"], "unavailable")
        self.assertNotIn("sensitive", json.dumps(result))
        self.assertEqual(ctx.writes, [])

    def test_failed_write_keeps_loaded_mode_and_redacts_error(self):
        class Unwritable(Context):
            def set_config(self, key, value):
                raise OSError("sensitive native error")

        ctx = Unwritable()
        load_entry().register(ctx)
        result = json.loads(ctx.commands["quota-router"]("mode observe"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["mode_effective"], "off")
        self.assertEqual(ctx.settings, {})
        self.assertNotIn("sensitive", json.dumps(result))

    def test_saved_auto_is_an_integrity_error_not_native_off(self):
        ctx = Context()
        ctx.settings["mode"] = "auto"
        load_entry().register(ctx)
        result = json.loads(ctx.commands["quota-router"]("status"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["mode_effective"], "unavailable")
        self.assertFalse(result["auto_available"])
        self.assertEqual(ctx.settings, {"mode": "auto"})
        recovery = json.loads(ctx.commands["quota-router"]("mode off"))
        self.assertTrue(recovery["ok"])
        self.assertEqual(recovery["mode_effective"], "off")


if __name__ == "__main__":
    unittest.main()
