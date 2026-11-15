"""S2 decision policy by scenario (HQR-20 scenario map A1-A15; AC-04 and AC-22 at decision level)."""
import unittest

from datetime import timedelta

from s2_fakes import CREDITS_EMPTY, CREDITS_OK, NOW, WEEK, Snapshot, Window, claude, codex, codex_rate_limit, settings
from quota_router.policy import decide, eligibility
from quota_router.readings import normalize


def readings(codex_snap, claude_snap):
    return {"openai-codex": normalize("openai-codex", codex_snap, NOW, 60),
            "anthropic": normalize("anthropic", claude_snap, NOW, 60)}


class PolicyTests(unittest.TestCase):
    def test_a1_both_available(self):
        r = readings(codex(50, week_reset_h=72), claude(21, week_reset_h=120))
        conversation = decide("conversation", r, settings(), NOW)
        self.assertEqual((conversation["choice"], conversation["tier"], conversation["reason"]),
                         ("openai-codex", "subscription", "principal_eligible"))
        route = decide("general", r, settings(), NOW)
        self.assertEqual((route["choice"], route["reason"]), ("openai-codex", "best_pacing"))
        self.assertGreater(route["scores"]["openai-codex"], route["scores"]["anthropic"])
        paced = decide("conversation", r, settings({"conversation.policy": "pacing"}), NOW)
        self.assertEqual(paced["reason"], "best_pacing")

    def test_a2_codex_exhausted_prefers_claude_subscription_over_codex_credits(self):
        r = readings(codex(100, credits=CREDITS_OK), claude(21))
        for role in ("conversation", "general"):
            decision = decide(role, r, settings(), NOW)
            self.assertEqual((decision["choice"], decision["tier"]), ("anthropic", "subscription"), role)

    def test_a3_claude_exhausted(self):
        decision = decide("general", readings(codex(40), claude(100)), settings(), NOW)
        self.assertEqual((decision["choice"], decision["tier"]), ("openai-codex", "subscription"))

    def test_a4_a5_a11_both_exhausted(self):
        r = readings(codex(100, credits=CREDITS_OK), claude(100))
        paid = decide("general", r, settings(), NOW)
        self.assertEqual((paid["choice"], paid["tier"]), ("openai-codex", "credits"))
        off = decide("general", r, settings({"credits.openai-codex": False}), NOW)
        self.assertEqual((off["choice"], off["tier"], off["reason"]), (None, None, "no_eligible_candidate"))
        self.assertEqual(len(off["resets"]), 2)
        empty = decide("general", readings(codex(100, credits=CREDITS_EMPTY), claude(100)), settings(), NOW)
        self.assertIsNone(empty["choice"])

    def test_a6_claude_session_window_blocks(self):
        result = eligibility(normalize("anthropic", claude(10, session_used=96), NOW, 60), settings(), NOW)
        self.assertEqual((result["subscription"], result["blocked_by"]), (False, "session"))
        edge = eligibility(normalize("anthropic", claude(10, session_used=95), NOW, 60), settings(), NOW)
        self.assertEqual(edge["blocked_by"], "session")
        below = eligibility(normalize("anthropic", claude(10, session_used=94), NOW, 60), settings(), NOW)
        self.assertTrue(below["subscription"])

    def test_a8_unknown_reading_is_never_capacity(self):
        r = {"openai-codex": normalize("openai-codex", None, NOW, 60), "anthropic": normalize("anthropic", claude(10), NOW, 60)}
        decision = decide("general", r, settings(), NOW)
        self.assertEqual(decision["choice"], "anthropic")
        self.assertTrue(decision["eligibility"]["openai-codex"]["blocked_by"].startswith("unknown:"))

    def test_a10_a14_hysteresis(self):
        # Codex score 0.5/0.5 = 1.0; Claude score 0.55/0.5 = 1.1 (exactly 10% more) and 0.56/0.5 = 1.12.
        exact = readings(codex(50, week_reset_h=84), claude(45, week_reset_h=84))
        kept = decide("general", exact, settings(), NOW, previous="openai-codex")
        self.assertEqual((kept["choice"], kept["reason"]), ("openai-codex", "previous_preference_kept"))
        above = readings(codex(50, week_reset_h=84), claude(44, week_reset_h=84))
        switched = decide("general", above, settings(), NOW, previous="openai-codex")
        self.assertEqual((switched["choice"], switched["reason"]), ("anthropic", "challenger_above_hysteresis"))

    def test_a13_conversation_returns_to_principal(self):
        decision = decide("conversation", readings(codex(5), claude(10)), settings(), NOW, previous="anthropic")
        self.assertEqual((decision["choice"], decision["reason"]), ("openai-codex", "principal_eligible"))

    def test_a15_anthropic_credits_not_verifiable(self):
        r = readings(codex(100), claude(100))
        decision = decide("general", r, settings({"credits.anthropic": True, "credits.openai-codex": False}), NOW)
        self.assertIsNone(decision["choice"])
        self.assertEqual(decision["eligibility"]["anthropic"]["credits_reason"], "credits_not_verifiable")

    def test_pacing_tie_goes_to_principal_and_model_window_scope(self):
        tie = decide("general", readings(codex(50, week_reset_h=84), claude(50, week_reset_h=84)), settings(), NOW)
        self.assertEqual(tie["choice"], "openai-codex")
        tie_claude = decide("general", readings(codex(50, week_reset_h=84), claude(50, week_reset_h=84)),
                            settings({"principal": "anthropic"}), NOW)
        self.assertEqual(tie_claude["choice"], "anthropic")
        opus_blocked = normalize("anthropic", claude(10, opus_used=100), NOW, 60)
        self.assertFalse(eligibility(opus_blocked, settings(), NOW, model="claude-opus-5-5")["subscription"])
        self.assertTrue(eligibility(opus_blocked, settings(), NOW, model="claude-sonnet-5-5")["subscription"])


class PolicyBoundaryTests(unittest.TestCase):
    def test_inconsistent_window_never_becomes_paid_capacity(self):
        far = Snapshot("openai-codex", "usage_api", NOW, (Window("Weekly", 50, NOW + timedelta(days=8)),),
                       raw={"credits": CREDITS_OK, "rate_limit": codex_rate_limit(WEEK)})
        r = {"openai-codex": normalize("openai-codex", far, NOW, 60), "anthropic": normalize("anthropic", claude(100), NOW, 60)}
        decision = decide("general", r, settings(), NOW)
        self.assertIsNone(decision["choice"])
        self.assertEqual(decision["eligibility"]["openai-codex"]["credits_reason"], "reading_inconsistent")

    def test_fractional_thresholds_and_strict_hysteresis_keep_full_precision(self):
        below = eligibility(normalize("anthropic", claude(10, session_used=94.99999), NOW, 60), settings(), NOW)
        self.assertTrue(below["subscription"])
        tiny = readings(codex(50, week_reset_h=84), claude(44.9999999995, week_reset_h=84))
        decision = decide("general", tiny, settings(), NOW, previous="openai-codex")
        self.assertEqual(decision["reason"], "challenger_above_hysteresis")

    def test_credit_limits_block_paid_codex(self):
        for extra in ({"overage_limit_reached": True}, {}):
            snap = codex(100, credits=dict(CREDITS_OK, **extra))
            if not extra:
                snap = Snapshot(snap.provider, snap.source, snap.fetched_at, snap.windows,
                                raw=dict(snap.raw, spend_control={"reached": True}))
            decision = decide("general", readings(snap, claude(100)), settings(), NOW)
            self.assertIsNone(decision["choice"], extra)

    def test_exhausted_inconsistent_window_never_becomes_paid_capacity(self):
        far = Snapshot("openai-codex", "usage_api", NOW, (Window("Weekly", 100, NOW + timedelta(days=8)),),
                       raw={"credits": CREDITS_OK, "spend_control": {"reached": False}, "rate_limit": codex_rate_limit(WEEK)})
        decision = decide("general", {"openai-codex": normalize("openai-codex", far, NOW, 60),
                                      "anthropic": normalize("anthropic", claude(100), NOW, 60)}, settings(), NOW)
        self.assertIsNone(decision["choice"])
        self.assertEqual(decision["eligibility"]["openai-codex"]["credits_reason"], "reading_inconsistent")
        long_session = Snapshot("openai-codex", "usage_api", NOW, (Window("Session", 10, NOW + timedelta(hours=6)),
                                                                   Window("Weekly", 10, NOW + timedelta(days=3))),
                                raw={"rate_limit": codex_rate_limit(18000, WEEK)})
        result = eligibility(normalize("openai-codex", long_session, NOW, 60), settings(), NOW)
        self.assertEqual(result["blocked_by"], "inconsistent_window")

    def test_credit_evidence_fails_closed(self):
        cases = ({"balance": "Infinity"}, {"balance": "nan"}, {"balance": True}, {"balance": "0", "unlimited": True})
        for change in cases:
            snap = codex(100, credits=dict(CREDITS_OK, **change))
            self.assertIsNone(decide("general", readings(snap, claude(100)), settings(), NOW)["choice"], change)
        no_overage = {k: v for k, v in CREDITS_OK.items() if k != "overage_limit_reached"}
        for snap in (codex(100, credits=no_overage), codex(100, credits=CREDITS_OK, spend_reached=None)):
            decision = decide("general", readings(snap, claude(100)), settings(), NOW)
            self.assertIsNone(decision["choice"])
            self.assertEqual(decision["eligibility"]["openai-codex"]["credits_reason"], "credits_limits_not_verifiable")
        self.assertEqual(decide("general", readings(codex(100, credits=CREDITS_OK), claude(100)), settings(), NOW)["choice"],
                         "openai-codex")

    def test_blocked_models_are_not_candidates(self):
        both = readings(codex(100), claude(10))
        decision = decide("deep", both, settings(), NOW, blocked={"anthropic": "model_not_eligible:fable"})
        self.assertIsNone(decision["choice"])
        self.assertEqual(decision["eligibility"]["anthropic"]["blocked_by"], "model_not_eligible:fable")
        self.assertFalse(decision["eligibility"]["anthropic"]["credits"])

    def test_upstream_denial_with_free_windows_is_contradictory(self):
        for snap in (codex(10, allowed=False), Snapshot("openai-codex", "usage_api", NOW,
                                                        (Window("Weekly", 10, NOW + timedelta(days=3)),),
                                                        raw={"rate_limit": dict(codex_rate_limit(WEEK), limit_reached=True),
                                                             "credits": CREDITS_OK, "spend_control": {"reached": False}})):
            decision = decide("general", readings(snap, claude(100)), settings(), NOW)
            self.assertIsNone(decision["choice"])
            self.assertEqual(decision["eligibility"]["openai-codex"]["blocked_by"], "upstream_denied_contradiction")
            self.assertEqual(decision["eligibility"]["openai-codex"]["credits_reason"], "reading_inconsistent")
        paid = decide("general", readings(codex(100, credits=CREDITS_OK, allowed=False), claude(100)), settings(), NOW)
        self.assertEqual((paid["choice"], paid["tier"]), ("openai-codex", "credits"))

    def test_session_limit_setting(self):
        tight = settings({"limits.session_block_pct": 50})
        self.assertEqual(eligibility(normalize("anthropic", claude(10, session_used=60), NOW, 60), tight, NOW)["blocked_by"],
                         "session")
        self.assertTrue(eligibility(normalize("anthropic", claude(10, session_used=60), NOW, 60), settings(), NOW)["subscription"])

    def test_settings_change_decisions(self):
        both = readings(codex(30, week_reset_h=84), claude(10, week_reset_h=84))
        self.assertEqual(decide("conversation", both, settings(), NOW)["choice"], "openai-codex")
        self.assertEqual(decide("conversation", both, settings({"conversation.policy": "pacing"}), NOW)["choice"], "anthropic")
        blocked = decide("general", readings(codex(85), claude(10)), settings({"limits.week_block_pct": 80}), NOW)
        self.assertEqual(blocked["eligibility"]["openai-codex"]["blocked_by"], "week")
        recovered = readings(codex(10, week_reset_h=84), claude(15, week_reset_h=84))
        kept = decide("general", recovered, settings(), NOW, previous="anthropic")
        self.assertEqual((kept["choice"], kept["reason"]), ("anthropic", "previous_preference_kept"))
        switched = decide("general", recovered, settings({"limits.hysteresis_pct": 0}), NOW, previous="anthropic")
        self.assertEqual(switched["choice"], "openai-codex")


if __name__ == "__main__":
    unittest.main()
