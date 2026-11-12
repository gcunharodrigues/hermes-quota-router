"""Concurrent management commands must not desynchronize saved/effective mode."""
import json
import threading
import unittest
from test_default import Context, load_entry


class ConcurrentTests(unittest.TestCase):
    def test_concurrent_off_cannot_be_overwritten_by_earlier_observe(self):
        entered = threading.Event()
        release = threading.Event()
        off_done = threading.Event()
        errors = []

        class ContextWithDelayedWrite(Context):
            def set_config(self, key, value):
                super().set_config(key, value)
                if value == "observe":
                    entered.set()
                    if not release.wait(3):
                        raise RuntimeError("test release missing")

        ctx = ContextWithDelayedWrite()
        load_entry().register(ctx)
        command = ctx.commands["quota-router"]

        def run(argument):
            try:
                command(argument)
            except Exception as error:
                errors.append(type(error).__name__)
            finally:
                if argument == "mode off":
                    off_done.set()

        first = threading.Thread(target=run, args=("mode observe",))
        second = threading.Thread(target=run, args=("mode off",))
        first.start()
        try:
            self.assertTrue(entered.wait(3))
            second.start()
            off_done.wait(0.1)
        finally:
            release.set()
            first.join(3)
            if second.ident is not None:
                second.join(3)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        status = json.loads(command("status"))
        self.assertEqual(status["mode_saved"], "off")
        self.assertEqual(status["mode_effective"], "off")
        self.assertFalse(status["restart_required"])


if __name__ == "__main__":
    unittest.main()
