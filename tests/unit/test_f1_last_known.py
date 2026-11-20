# decision D-35: a failed fetch decides on the last known reading.
from datetime import datetime, timedelta, timezone
import unittest

from quota_router import readings

NOW = datetime(2026, 11, 18, 23, 0, tzinfo=timezone.utc)


def good(fetched, session_reset, week_reset, session_pct=30.0, week_pct=45.0):
    return {"provider": "anthropic", "state": "ok", "reason": None, "source": "oauth_usage_api",
            "fetched_at": fetched.isoformat(), "age_s": 0.0, "credits": {"visible": False}, "astra_available": None,
            "upstream": {"allowed": None, "limit_reached": None},
            "windows": [
                {"kind": "session", "duration_s": 18000, "family": None, "reset_at": session_reset.isoformat(),
                 "used": session_pct / 100, "used_pct": session_pct},
                {"kind": "week", "duration_s": 604800, "family": None, "reset_at": week_reset.isoformat(),
                 "used": week_pct / 100, "used_pct": week_pct}]}


def failing(provider):
    raise RuntimeError("usage endpoint down")


class LastKnownTests(unittest.TestCase):
    def test_failed_fetch_uses_last_known_reading(self):
        last = {"anthropic": good(NOW - timedelta(minutes=20), NOW + timedelta(hours=2), NOW + timedelta(days=5))}
        found, _ = readings.collect(["anthropic"], NOW, 300, reader=failing, cache={}, last_good=last)
        reading = found["anthropic"]
        self.assertEqual(reading["state"], "ok")
        self.assertTrue(reading["last_known"])
        self.assertEqual([w["used_pct"] for w in reading["windows"]], [30.0, 45.0])

    def test_without_last_known_a_failure_stays_unknown(self):
        found, _ = readings.collect(["anthropic"], NOW, 300, reader=failing, cache={}, last_good={})
        self.assertEqual(found["anthropic"]["state"], "unknown")

    # Revisão F1–F5, R5: a window renewed while carried is not 0% used; the policy reads its passed reset as unknown.
    def test_elapsed_window_is_not_taken_as_renewed(self):
        from quota_router.policy import eligibility
        from quota_router.settings import DEFAULTS
        passed = NOW - timedelta(minutes=1)
        last = {"anthropic": good(NOW - timedelta(hours=3), passed, NOW + timedelta(days=5), 99.0)}
        found, _ = readings.collect(["anthropic"], NOW, 300, reader=failing, cache={}, last_good=last)
        session = found["anthropic"]["windows"][0]
        self.assertEqual((session["used_pct"], session["reset_at"]), (99.0, passed.isoformat()))
        state = eligibility(readings.revalidate(found, NOW, 300)["anthropic"], dict(DEFAULTS), NOW)
        self.assertEqual((state["state"], state["blocked_by"]), ("unknown", "reset_passed"))

    def test_too_old_last_known_is_not_used(self):
        old = NOW - timedelta(seconds=readings.LAST_KNOWN_MAX_AGE_S + 1)
        last = {"anthropic": good(old, NOW + timedelta(hours=2), NOW + timedelta(days=5))}
        found, _ = readings.collect(["anthropic"], NOW, 300, reader=failing, cache={}, last_good=last)
        self.assertEqual(found["anthropic"]["state"], "unknown")

    def test_success_updates_last_known_and_revalidation_keeps_carried_reading(self):
        last = {}
        fresh = good(NOW, NOW + timedelta(hours=2), NOW + timedelta(days=5))
        readings.collect(["anthropic"], NOW, 300, reader=lambda p: None, cache={"anthropic": fresh}, last_good=last)
        self.assertIn("anthropic", last)
        later = NOW + timedelta(hours=1)
        found, _ = readings.collect(["anthropic"], later, 300, reader=failing, cache={}, last_good=last)
        kept = readings.revalidate(found, later, 300)
        self.assertEqual(kept["anthropic"]["state"], "ok")
        self.assertTrue(kept["anthropic"]["last_known"])


if __name__ == "__main__":
    unittest.main()
