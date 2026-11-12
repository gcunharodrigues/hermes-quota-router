"""Exact payload checks operate on disposable synthetic trees only."""
import importlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


class PayloadTests(unittest.TestCase):
    def test_exact_hashes_reject_changed_missing_extra_and_symlink_files(self):
        self.assertIsNotNone(importlib.util.find_spec("quota_router.verification"), "Payload verification missing")
        verify = importlib.import_module("quota_router.verification")
        with tempfile.TemporaryDirectory(prefix="hqr-payload-") as directory:
            root = Path(directory)
            (root / "module.py").write_text("original\n", encoding="utf-8")
            expected = verify.hash_tree(root, ["module.py"])
            self.assertEqual(len(expected["module.py"]), 64)
            self.assertEqual(verify.verify_tree(root, expected), [])
            (root / "module.py").write_text("modified\n", encoding="utf-8")
            self.assertIn("modified:module.py", verify.verify_tree(root, expected))
            (root / "module.py").unlink()
            self.assertIn("missing:module.py", verify.verify_tree(root, expected))
            (root / "module.py").write_text("original\n", encoding="utf-8")
            (root / "ignored.py").write_text("leftover\n", encoding="utf-8")
            self.assertIn("extra:ignored.py", verify.verify_tree(root, expected))
            (root / "ignored.py").unlink()
            (root / "module.py").unlink()
            (root / "module.py").symlink_to(root / "elsewhere")
            with self.assertRaises(ValueError):
                verify.verify_tree(root, expected)
            (root / "module.py").unlink()
            (root / "module.py").write_text("original\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                verify.hash_tree(root, ["../escape"])
            with self.assertRaises(ValueError):
                verify.hash_tree(root, ["module.py", "module.py"])
            with self.assertRaises(ValueError):
                verify.verify_tree(root, {"module.py": "not-a-hash"})
            (root / ".git").mkdir()
            (root / ".git" / "metadata").write_text("native metadata", encoding="utf-8")
            self.assertEqual(verify.verify_tree(root, expected), [])
            (root / "auth.json").write_text("synthetic forbidden filename", encoding="utf-8")
            with self.assertRaises(ValueError):
                verify.hash_tree(root, ["module.py", "auth.json"])


if __name__ == "__main__":
    unittest.main()
