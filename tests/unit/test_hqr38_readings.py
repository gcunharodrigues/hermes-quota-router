"""HQR-38 reading fixes by plan type (decisions/hqr-38-spec.md, "Correções de leitura e tipos de plano").

Snapshots mirror the native `agent/account_usage.py` shapes: Anthropic windows without raw, Codex windows plus raw payload.
All values are synthetic; no Hermes import, network or real account.
"""
from datetime import timedelta
import unittest

from s2_fakes import CREDITS_OK, NOW, WEEK, Snapshot, Window, claude, codex, codex_rate_limit, reader_for, settings
from quota_router.policy import decide, eligibility
from quota_router.readings import collect, normalize, revalidate

CODEX, CLAUDE = "openai-codex", "anthropic"


def codex_raw(windows, raw):
    return Snapshot(CODEX, "usage_api", NOW, tuple(windows), raw=raw)


def extra_limit(name, used, seconds=WEEK, reset=NOW + timedelta(days=3)):
    window = {"used_percent": used, "limit_window_seconds": seconds, "reset_at": int(reset.timestamp())}
    return {"limit_name": name, "metered_feature": "synthetic_feature",
            "rate_limit": {"allowed": used < 100, "limit_reached": used >= 100, "primary_window": window}}


def with_extra(snapshot, *limits):
    return Snapshot(snapshot.provider, snapshot.source, snapshot.fetched_at, snapshot.windows,
                    raw=dict(snapshot.raw, additional_rate_limits=list(limits)))


class IdleWindowTests(unittest.TestCase):
    """A22: the native reader keeps a Claude window whose `resets_at` is null."""

    def test_idle_session_and_model_window_do_not_invalidate_the_reading(self):
        snap = Snapshot(CLAUDE, "oauth_usage_api", NOW, (
            Window("Current session", 0, None), Window("Current week", 30, NOW + timedelta(hours=120)),
            Window("Sonnet week", 12.5, None, scope="model")))
        reading = normalize(CLAUDE, snap, NOW, 60)
        self.assertEqual(reading["state"], "ok", reading)
        session = next(w for w in reading["windows"] if w["kind"] == "session")
        self.assertEqual((session["used_pct"], session["reset_at"]), (0, None))
        self.assertEqual(eligibility(reading, settings(), NOW, model="claude-opus-5-5")["state"], "free")
        self.assertEqual(eligibility(reading, settings(), NOW, model="claude-sonnet-5-5")["state"], "unknown")

    def test_idle_week_counts_as_a_full_window_ahead(self):
        snap = Snapshot(CLAUDE, "oauth_usage_api", NOW, (Window("Current week", 0, None),))
        reading = normalize(CLAUDE, snap, NOW, 60)
        verdict = eligibility(reading, settings(), NOW)
        self.assertEqual((verdict["state"], verdict["score"]), ("free", 1.0))
        self.assertEqual(verdict["resets"], [])

    def test_used_week_without_reset_still_fails_closed(self):
        snap = Snapshot(CLAUDE, "oauth_usage_api", NOW, (Window("Current week", 30, None),))
        self.assertEqual(normalize(CLAUDE, snap, NOW, 60)["reason"], "malformed_window")

    def test_idle_windows_survive_cache_and_decision_time_revalidation(self):
        snap = Snapshot(CLAUDE, "oauth_usage_api", NOW, (
            Window("Current session", 0, None), Window("Current week", 30, NOW + timedelta(hours=120))))
        cache = {}
        found, _ = collect((CLAUDE,), NOW, 60, reader=reader_for(anthropic=snap), cache=cache)
        later, queries = collect((CLAUDE,), NOW + timedelta(seconds=20), 60, reader=reader_for(anthropic=snap), cache=cache)
        self.assertEqual((found[CLAUDE]["state"], later[CLAUDE]["state"], queries), ("ok", "ok", 0))
        self.assertEqual(revalidate(later, NOW + timedelta(seconds=30), 60)[CLAUDE]["state"], "ok")


class ClockToleranceTests(unittest.TestCase):
    """A23: a not-started Codex window may report reset_at slightly beyond now + duration."""

    def test_not_started_window_one_second_ahead_is_free(self):
        snap = codex_raw((Window("Weekly", 0, NOW + timedelta(seconds=WEEK + 1)),), {"rate_limit": codex_rate_limit(WEEK)})
        verdict = eligibility(normalize(CODEX, snap, NOW, 60), settings(), NOW)
        self.assertEqual(verdict["state"], "free")

    def test_inconsistency_beyond_tolerance_never_blocks_verified_credits_by_itself(self):
        raw = {"rate_limit": codex_rate_limit(WEEK), "credits": CREDITS_OK, "spend_control": {"reached": False}}
        far = codex_raw((Window("Weekly", 100, NOW + timedelta(days=8)),), raw)
        found = {CODEX: normalize(CODEX, far, NOW, 60), CLAUDE: normalize(CLAUDE, claude(100), NOW, 60)}
        decision = decide("general", found, settings(), NOW)
        self.assertEqual(decision["eligibility"][CODEX]["state"], "unknown")
        self.assertEqual(decision["eligibility"][CODEX]["blocked_by"], "inconsistent_window")
        self.assertEqual((decision["choice"], decision["tier"]), (CODEX, "credits"))
        disabled = decide("general", found, settings({"credits.openai-codex": False}), NOW)
        self.assertIsNone(disabled["choice"])


class StructuralRetryTests(unittest.TestCase):
    """A29: structural reasons retry on the next cycle instead of the 300 s failure backoff."""

    def test_structural_reasons_retry_after_the_minimum_interval(self):
        cases = {"reset_passed": Snapshot(CLAUDE, "oauth_usage_api", NOW, (Window("Current week", 10, NOW),)),
                 "stale_reading": claude(10, fetched_at=NOW - timedelta(seconds=61)),
                 "future_reading": claude(10, fetched_at=NOW + timedelta(seconds=5))}
        for reason, snap in cases.items():
            with self.subTest(reason=reason):
                reader, cache = reader_for(anthropic=snap), {}
                first, _ = collect((CLAUDE,), NOW, 60, reader=reader, cache=cache)
                self.assertEqual(first[CLAUDE]["reason"], reason)
                self.assertEqual(first[CLAUDE]["retry_at"], (NOW + timedelta(seconds=30)).isoformat())
                _, issued = collect((CLAUDE,), NOW + timedelta(seconds=30), 60, reader=reader, cache=cache)
                self.assertEqual(issued, 1)

    def test_transport_failures_keep_the_failure_backoff(self):
        reader, cache = reader_for(anthropic=None), {}
        first, _ = collect((CLAUDE,), NOW, 60, reader=reader, cache=cache)
        self.assertEqual(first[CLAUDE]["retry_at"], (NOW + timedelta(seconds=300)).isoformat())


class ModelLimitTests(unittest.TestCase):
    """A31: Codex `additional_rate_limits` block only the model they name."""

    def test_exhausted_additional_limit_blocks_only_its_model(self):
        reading = normalize(CODEX, with_extra(codex(10), extra_limit("GPT-6.1-Terra", 100)), NOW, 60)
        self.assertEqual(reading["state"], "ok")
        terra = eligibility(reading, settings(), NOW, model="gpt-6.1-terra")
        self.assertEqual((terra["state"], terra["blocked_by"]), ("exhausted", "week"))
        self.assertEqual(eligibility(reading, settings(), NOW, model="gpt-6.1-sol")["state"], "free")

    def test_unrelated_additional_limit_does_not_touch_the_mapped_models(self):
        reading = normalize(CODEX, with_extra(codex(10), extra_limit("GPT-5.3-Codex-Spark", 100)), NOW, 60)
        for model in ("gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-luna"):
            self.assertEqual(eligibility(reading, settings(), NOW, model=model)["state"], "free", model)

    def test_additional_session_limit_can_press_its_model(self):
        reading = normalize(CODEX, with_extra(codex(10), extra_limit("gpt-6.1-terra", 96, seconds=18000,
                                                                    reset=NOW + timedelta(hours=2))), NOW, 60)
        self.assertEqual(eligibility(reading, settings(), NOW, model="gpt-6.1-terra")["state"], "pressured")

    def test_unqualified_additional_duration_fails_closed_for_its_model_only(self):
        reading = normalize(CODEX, with_extra(codex(10), extra_limit("gpt-6.1-terra", 10, seconds=86400,
                                                                    reset=NOW + timedelta(hours=10))), NOW, 60)
        self.assertEqual(eligibility(reading, settings(), NOW, model="gpt-6.1-terra")["state"], "unknown")
        self.assertEqual(eligibility(reading, settings(), NOW, model="gpt-6.1-sol")["state"], "free")


class OverHundredTests(unittest.TestCase):
    """A32: usage above 100% is clamped and counts as exhausted."""

    def test_usage_above_one_hundred_is_exhausted_and_may_use_credits(self):
        reading = normalize(CLAUDE, claude(120), NOW, 60)
        self.assertEqual(reading["state"], "ok")
        self.assertEqual(reading["windows"][0]["used_pct"], 100)
        self.assertEqual(eligibility(reading, settings(), NOW)["state"], "exhausted")
        found = {CODEX: normalize(CODEX, codex(130, credits=CREDITS_OK), NOW, 60), CLAUDE: reading}
        decision = decide("general", found, settings(), NOW)
        self.assertEqual((decision["choice"], decision["tier"]), (CODEX, "credits"))

    def test_negative_usage_still_fails_closed(self):
        snap = Snapshot(CLAUDE, "x", NOW, (Window("Current week", -1, NOW + timedelta(days=1)),))
        self.assertEqual(normalize(CLAUDE, snap, NOW, 60)["reason"], "malformed_window")


class NullUsageDurationTests(unittest.TestCase):
    """A38: the native reader skips a Codex window without usage; duration evidence must skip it too."""

    def test_window_without_numeric_usage_is_not_counted(self):
        rate_limit = {"primary_window": {"used_percent": None, "limit_window_seconds": 18000},
                      "secondary_window": {"used_percent": 20, "limit_window_seconds": WEEK}}
        snap = codex_raw((Window("Weekly", 20, NOW + timedelta(days=3)),), {"rate_limit": rate_limit})
        self.assertEqual(normalize(CODEX, snap, NOW, 60)["state"], "ok")


class PlanTypeTests(unittest.TestCase):
    def test_a26_monthly_plan_has_an_explicit_reason(self):
        monthly = {"primary_window": {"used_percent": 30, "limit_window_seconds": 2592000}}
        for raw in ({"plan_type": "go", "rate_limit": monthly}, {"plan_type": "plus", "rate_limit": monthly},
                    {"plan_type": "go", "rate_limit": {}}):
            with self.subTest(raw=raw):
                windows = (Window("Session", 30, NOW + timedelta(days=20)),) if raw["rate_limit"] else ()
                reading = normalize(CODEX, codex_raw(windows, raw), NOW, 60)
                self.assertEqual((reading["state"], reading["reason"]), ("unknown", "monthly_plan_unsupported"))

    def test_a27_credits_only_plan_is_exhausted_with_credits(self):
        raw = {"plan_type": "enterprise", "rate_limit": {"allowed": True, "limit_reached": False},
               "credits": CREDITS_OK, "spend_control": {"reached": False}}
        reading = normalize(CODEX, codex_raw((), raw), NOW, 60)
        self.assertEqual((reading["state"], reading.get("credits_only")), ("ok", True))
        verdict = eligibility(reading, settings(), NOW)
        self.assertEqual((verdict["state"], verdict["blocked_by"], verdict["credits"]), ("exhausted", "credits_only_plan", True))
        exhausted = {CODEX: reading, CLAUDE: normalize(CLAUDE, claude(100), NOW, 60)}
        self.assertEqual(decide("general", exhausted, settings(), NOW)["tier"], "credits")
        free = {CODEX: reading, CLAUDE: normalize(CLAUDE, claude(10), NOW, 60)}
        self.assertEqual(decide("general", free, settings(), NOW)["choice"], CLAUDE)
        self.assertIsNone(decide("general", exhausted, settings({"credits.openai-codex": False}), NOW)["choice"])

    def test_a27_missing_windows_without_credit_evidence_stay_unknown(self):
        reading = normalize(CODEX, codex_raw((), {"rate_limit": {}}), NOW, 60)
        self.assertEqual((reading["state"], reading["reason"]), ("unknown", "no_week_window"))

    def test_a34_new_window_format_requires_requalification(self):
        rate_limit = dict(codex_rate_limit(WEEK), tertiary_window={"used_tokens": 10, "limit_tokens": 100})
        raw = {"rate_limit": rate_limit, "credits": CREDITS_OK, "spend_control": {"reached": False}}
        reading = normalize(CODEX, codex_raw((Window("Weekly", 10, NOW + timedelta(days=3)),), raw), NOW, 60)
        self.assertEqual((reading["state"], reading["reason"]), ("unknown", "format_requalification_required"))
        self.assertTrue(reading["requalification_required"])
        found = {CODEX: reading, CLAUDE: normalize(CLAUDE, claude(100), NOW, 60)}
        self.assertIsNone(decide("general", found, settings(), NOW)["choice"])

    def test_a34_unqualified_duration_is_flagged_for_requalification(self):
        snap = codex_raw((Window("Weekly", 10, NOW + timedelta(days=1)),), {"rate_limit": codex_rate_limit(86400)})
        reading = normalize(CODEX, snap, NOW, 60)
        self.assertEqual(reading["reason"], "window_duration_unqualified")
        self.assertTrue(reading["requalification_required"])


if __name__ == "__main__":
    unittest.main()
