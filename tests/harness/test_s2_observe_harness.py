"""Pure helpers of the S2 installed runner (tests/installed/s2_observe.py); no Docker, no Hermes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests" / "installed"))

import s2_observe  # noqa: E402
from lifecycle import Failure  # noqa: E402

A, B = "a" * 40, "b" * 40


def status(**overrides):
    reading = {"state": "unknown", "reason": "no_snapshot"}
    base = {"ok": True, "mode_effective": "observe", "quota_queries": 2, "extra_inferences": 0, "decision_incomplete": True,
            "auto_available": False, "quota": {"state": "observed", "source": "native_account_usage",
                                               "providers": {"openai-codex": dict(reading), "anthropic": dict(reading)}}}
    base.update(overrides)
    return base


class RunnerHelperTests(unittest.TestCase):
    def test_arguments_require_distinct_full_shas(self):
        self.assertEqual(s2_observe.parse(["r", "--candidate", A, "--rollback", B]).candidate, A)
        for argv in (["r", "--candidate", A[:12], "--rollback", B], ["r", "--candidate", A, "--rollback", A],
                     ["r", "--candidate", "main", "--rollback", B], ["r", "--candidate", A]):
            with self.assertRaises(SystemExit):
                s2_observe.parse(argv)

    def test_file_changes_allow_only_config_and_host_owned_paths(self):
        new = "backups/config/config.yaml.good.20261115-180000"
        before = {"config.yaml": "1", "logs/agent.log": "1", "memories/x.md": "1"}
        after = {"config.yaml": "2", "logs/agent.log": "2", "memories/x.md": "1", new: "3", ".config.yaml.lock": "4"}
        changes = s2_observe.file_changes(before, after)
        self.assertEqual(s2_observe.unexpected_changes(changes, after, {new: True}), [])
        self.assertEqual(s2_observe.unexpected_changes(changes, after, {new: False}), [new])
        self.assertEqual(s2_observe.unexpected_changes(changes, after), [new])
        after.update({"memories/x.md": "2", "cron/jobs.json": "5", "backups/other": "6", "logs/new.log": "7",
                      "backups/config/config.yaml.corrupt.20261115-180001": "8"})
        changes = s2_observe.file_changes(before, after)
        self.assertEqual(s2_observe.unexpected_changes(changes, after, {new: True}),
                         ["backups/config/config.yaml.corrupt.20261115-180001", "backups/other", "cron/jobs.json", "logs/new.log", "memories/x.md"])

    def test_deletions_only_by_backup_rotation(self):
        old = [f"backups/config/config.yaml.good.20261115-10000{i}" for i in range(5)]
        new = "backups/config/config.yaml.good.20261115-180000"
        before = {p: "x" for p in old}
        after = {p: "x" for p in old[1:]}
        after[new] = "y"
        changes = s2_observe.file_changes(before, after)
        self.assertEqual(s2_observe.unexpected_changes(changes, after, {new: True}), [])
        middle = {p: "x" for p in old if p != old[2]}
        middle[new] = "y"
        # Wrong backup rotated: the deleted one and the one that should have gone are both reported.
        self.assertEqual(s2_observe.unexpected_changes(s2_observe.file_changes(before, middle), middle, {new: True}), [old[0], old[2]])
        # Two new backups over five kept: the host deletes the two oldest; keeping the second one is reported.
        crowded = dict(after)
        crowded["backups/config/config.yaml.good.20261115-170000"] = "z"
        self.assertEqual(s2_observe.unexpected_changes(s2_observe.file_changes(before, crowded), crowded,
                                                       {new: True, "backups/config/config.yaml.good.20261115-170000": True}), [old[1]])
        five = {p: "x" for p in old}
        no_addition = {p: "x" for p in old[1:]}
        self.assertEqual(s2_observe.unexpected_changes(s2_observe.file_changes(five, no_addition), no_addition), [old[0]])
        excessive = {old[4]: "x", new: "y"}
        self.assertEqual(s2_observe.unexpected_changes(s2_observe.file_changes(five, excessive), excessive, {new: True}),
                         old[1:4])
        kept = dict(five)
        kept[new] = "y"
        self.assertEqual(s2_observe.unexpected_changes(s2_observe.file_changes(five, kept), kept, {new: True}), [old[0]])
        three = {p: "x" for p in old[:3]}
        grown = dict(three, **{new: "y"})
        self.assertEqual(s2_observe.unexpected_changes(s2_observe.file_changes(three, grown), grown, {new: True}), [])
        for removed in ({"logs/agent.log": "1"}, {"skills/a": "1"}):
            self.assertEqual(s2_observe.unexpected_changes(s2_observe.file_changes(removed, {}), {}), list(removed))

    def test_inactive_install_and_effective_off(self):
        self.assertTrue(s2_observe.inactive("Name: x\nStatus: disabled\n"))
        self.assertTrue(s2_observe.inactive("Status: not enabled"))
        self.assertFalse(s2_observe.inactive("Status: enabled"))
        off = {"ok": True, "mode_effective": "off", "mode_saved": "off", "restart_required": False}
        s2_observe.require_off(off, off)
        for bad in (dict(off, ok=False), dict(off, mode_effective="observe"), dict(off, mode_saved="observe")):
            with self.assertRaises(Failure):
                s2_observe.require_off(bad, off)
        with self.assertRaises(Failure):
            s2_observe.require_off(off, dict(off, restart_required=True))

    def test_settings_changed_lists_keys(self):
        before = {"entry": {"settings": {"mode": "off", "roles": {}}}}
        after = {"entry": {"settings": {"mode": "observe", "roles": {}, "credits.anthropic": False}}}
        self.assertEqual(s2_observe.settings_changed(before, after), ["credits.anthropic", "mode"])
        self.assertEqual(s2_observe.settings_changed({"entry": None}, {"entry": None}), [])

    def test_observe_contract_rejects_known_readings_and_counters(self):
        self.assertEqual(s2_observe.observe_contract(status(), 2), {"openai-codex": "no_snapshot", "anthropic": "no_snapshot"})
        known = status()
        known["quota"]["providers"]["anthropic"] = {"state": "ok", "reason": None}
        for bad, queries in ((known, 2), (status(), 4), (status(extra_inferences=1), 2), (status(auto_available=True), 2),
                             (status(decision_incomplete=False), 2), (status(quota={"state": "unknown", "source": None}), 2)):
            with self.assertRaises(Failure):
                s2_observe.observe_contract(bad, queries)


if __name__ == "__main__":
    unittest.main()
