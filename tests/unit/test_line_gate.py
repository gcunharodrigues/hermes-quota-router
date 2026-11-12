"""Gate behavior has boundary, negative and operational-failure controls."""
import importlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


class LineGateTests(unittest.TestCase):
    def test_line_gate_enforces_2000_and_exact_exemptions(self):
        self.assertIsNotNone(importlib.util.find_spec("quota_router.line_gate"), "Authored-line gate missing")
        gate = importlib.import_module("quota_router.line_gate")
        with tempfile.TemporaryDirectory(prefix="hqr-lines-") as directory:
            root = Path(directory)
            path = root / "authored.md"
            path.write_text("x" * 2000 + "\n", encoding="utf-8")
            self.assertEqual(gate.check_lines(root, ["authored.md"]), [])
            path.write_text("x" * 2001 + "\n", encoding="utf-8")
            self.assertEqual(gate.check_lines(root, ["authored.md"]), ["authored.md:1:2001"])
            (root / "LICENSE").write_text("x" * 2001, encoding="utf-8")
            self.assertEqual(gate.check_lines(root, ["LICENSE"]), [])
            self.assertIn("LICENSE", gate.EXEMPTIONS)
            (root / "evidence").mkdir()
            (root / "evidence/new.txt").write_text("x" * 2001, encoding="utf-8")
            self.assertEqual(gate.check_lines(root, ["evidence/new.txt"]), ["evidence/new.txt:1:2001"])
            with self.assertRaises(OSError):
                gate.check_lines(root, ["missing.md"])
            with self.assertRaises(ValueError):
                gate.check_lines(root, ["../escape.md"])


if __name__ == "__main__":
    unittest.main()
