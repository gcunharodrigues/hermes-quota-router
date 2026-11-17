"""Published-head guard of the D1 pilot (tests/installed/s2_pilot.py); no Hermes, no network."""
import argparse
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests/installed"))

import s2_pilot  # noqa: E402
from lifecycle import Failure  # noqa: E402

A, B = "a" * 40, "b" * 40
BRANCH = "hermes/2026-11-15-hqr-s2-readable"


class PublishedHeadTests(unittest.TestCase):
    def test_exact_single_ref_at_candidate_passes(self):
        self.assertEqual(s2_pilot.published_head(f"{A}\trefs/heads/{BRANCH}\n", BRANCH, A), [[A, f"refs/heads/{BRANCH}"]])

    def test_missing_wrong_multiple_and_mismatch_fail(self):
        cases = {"missing": "", "sha": f"{B}\trefs/heads/{BRANCH}\n", "ref": f"{A}\trefs/heads/other\n",
                 "multiple": f"{A}\trefs/heads/{BRANCH}\n{A}\trefs/heads/{BRANCH}-x\n"}
        for name, output in cases.items():
            with self.subTest(name), self.assertRaises(Failure):
                s2_pilot.published_head(output, BRANCH, A)

    def test_branch_argument_is_literal(self):
        self.assertEqual(s2_pilot.branch_arg(BRANCH), BRANCH)
        for bad in ("hermes/2026-11-15-hqr-s2*", "a?b", "a[b]", "", "a//b", "../x", "a/.hidden", "a.lock", "a..b", "-", "a b"):
            with self.subTest(bad), self.assertRaises(argparse.ArgumentTypeError):
                s2_pilot.branch_arg(bad)


class PilotHomeTests(unittest.TestCase):
    def test_checks_and_cli_share_hermes_home(self):
        import importlib
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"HERMES_HOME": "/srv/other-home"}):
            module = importlib.reload(s2_pilot)
            self.assertEqual(module.HOME, Path("/srv/other-home"))
            self.assertNotIn("HQR_PILOT_HERMES_HOME", Path(module.__file__).read_text())
        importlib.reload(s2_pilot)


if __name__ == "__main__":
    unittest.main()
