"""HQR-38 switching policy: Livre, Pressionado, Esgotado and Desconhecido states (decisions/hqr-38-spec.md, D-31).

Synthetic native-shaped snapshots only; no Hermes import, network or real quota.
"""
import unittest

from s2_fakes import CREDITS_OK, NOW, claude, codex, settings
from quota_router.policy import decide, eligibility, fallback_chain
from quota_router.readings import normalize

CODEX, CLAUDE = "openai-codex", "anthropic"
# Session usage per stage for a provider that has a 5 h window; week-only providers skip the pressured stage.
STAGES = {"free": 50, "pressured": 97, "exhausted": 100}


def read(codex_snap, claude_snap):
    return {CODEX: normalize(CODEX, codex_snap, NOW, 60), CLAUDE: normalize(CLAUDE, claude_snap, NOW, 60)}


def snapshot(provider, shape, stage, week=30, credits=None):
    """One provider at a stage: 5 h + week moves the session window; week-only moves the week window."""
    if shape == "session+week":
        session = STAGES[stage]
        if provider == CODEX:
            return codex(week, session_used=session, credits=credits)
        return claude(week, session_used=session)
    used = 100 if stage == "exhausted" else week
    return codex(used, credits=credits) if provider == CODEX else claude(used)


class StateTests(unittest.TestCase):
    def test_states_follow_d31_thresholds(self):
        cases = ((claude(30, session_used=94.999), "free"), (claude(30, session_used=95), "pressured"),
                 (claude(30, session_used=99.999), "pressured"), (claude(30, session_used=100), "exhausted"),
                 (claude(100), "exhausted"), (claude(99.9), "free"), (None, "unknown"))
        for snap, expected in cases:
            with self.subTest(expected=expected, snap=snap):
                verdict = eligibility(normalize(CLAUDE, snap, NOW, 60), settings(), NOW)
                self.assertEqual(verdict["state"], expected)

    def test_pressured_is_not_free_and_reports_the_session_trigger(self):
        verdict = eligibility(normalize(CLAUDE, claude(30, session_used=97), NOW, 60), settings(), NOW)
        self.assertEqual((verdict["state"], verdict["subscription"], verdict["pressured"]), ("pressured", False, True))
        self.assertIsNotNone(verdict["score"])
        self.assertFalse(verdict["credits"])

    def test_model_week_counts_as_week_for_its_model_only(self):
        reading = normalize(CLAUDE, claude(10, opus_used=100), NOW, 60)
        self.assertEqual(eligibility(reading, settings(), NOW, model="claude-opus-5-5")["state"], "exhausted")
        self.assertEqual(eligibility(reading, settings(), NOW, model="claude-sonnet-5-5")["state"], "free")

    def test_decision_reports_states_per_provider(self):
        decision = decide("general", read(codex(10, session_used=97), claude(10)), settings(), NOW)
        self.assertEqual(decision["states"], {CODEX: "pressured", CLAUDE: "free"})


class PairMatrixTests(unittest.TestCase):
    """Claude {5 h + week, week-only} x Codex {5 h + week, week-only}, each side moving through its stages."""

    def test_moving_side_leaves_for_a_free_peer_and_never_uses_credits_while_a_subscription_serves(self):
        shapes = ("session+week", "week-only")
        for codex_shape in shapes:
            for claude_shape in shapes:
                for moving in (CODEX, CLAUDE):
                    moving_shape = codex_shape if moving == CODEX else claude_shape
                    other = CLAUDE if moving == CODEX else CODEX
                    other_shape = claude_shape if moving == CODEX else codex_shape
                    for stage in STAGES:
                        if stage == "pressured" and moving_shape == "week-only":
                            continue
                        with self.subTest(codex=codex_shape, claude=claude_shape, moving=moving, stage=stage):
                            snaps = {moving: snapshot(moving, moving_shape, stage, credits=CREDITS_OK),
                                     other: snapshot(other, other_shape, "free", week=60, credits=CREDITS_OK)}
                            found = read(snaps[CODEX], snaps[CLAUDE])
                            decision = decide("general", found, settings(), NOW, previous=moving)
                            self.assertEqual(decision["states"][moving], stage)
                            self.assertEqual(decision["states"][other], "free")
                            if stage == "free":
                                # Both free: the moving side keeps its preference (it has more weekly slack).
                                self.assertEqual((decision["choice"], decision["tier"]), (moving, "subscription"))
                            else:
                                # Group change ignores hysteresis even though the moving side has more weekly slack.
                                self.assertEqual((decision["choice"], decision["tier"]), (other, "subscription"))

    def test_both_sides_pressured_rank_by_weekly_slack_for_every_role(self):
        for role in ("conversation", "general"):
            with self.subTest(role=role):
                found = read(codex(60, session_used=96), claude(20, session_used=98))
                decision = decide(role, found, settings(), NOW)
                self.assertEqual((decision["choice"], decision["tier"]), (CLAUDE, "subscription"))
                self.assertEqual(decision["reason"], "pressured_best_pacing")

    def test_both_exhausted_use_allowed_credits_or_nothing(self):
        for codex_snap in (codex(30, session_used=100, credits=CREDITS_OK), codex(100, credits=CREDITS_OK)):
            for claude_snap in (claude(30, session_used=100), claude(100)):
                with self.subTest(codex=codex_snap.windows, claude=claude_snap.windows):
                    found = read(codex_snap, claude_snap)
                    paid = decide("general", found, settings(), NOW)
                    self.assertEqual((paid["choice"], paid["tier"]), (CODEX, "credits"))
                    off = decide("general", found, settings({"credits.openai-codex": False}), NOW)
                    self.assertEqual((off["choice"], off["reason"]), (None, "no_eligible_candidate"))


class ScenarioTests(unittest.TestCase):
    def test_a16_codex_session_pressured_claude_free(self):
        decision = decide("conversation", read(codex(10, session_used=96), claude(40)), settings(), NOW)
        self.assertEqual((decision["choice"], decision["tier"]), (CLAUDE, "subscription"))

    def test_a17_both_pressured_stay_on_subscription_even_with_visible_codex_credits(self):
        found = read(codex(20, session_used=96, credits=CREDITS_OK), claude(50, session_used=97))
        decision = decide("general", found, settings(), NOW)
        self.assertEqual((decision["choice"], decision["tier"]), (CODEX, "subscription"))
        self.assertNotEqual(decision["tier"], "credits")
        self.assertEqual(decision["states"], {CODEX: "pressured", CLAUDE: "pressured"})

    def test_a18_both_sessions_exhausted_without_usable_credits(self):
        for overrides, snap in (({"credits.openai-codex": False}, codex(10, session_used=100, credits=CREDITS_OK)),
                                ({}, codex(10, session_used=100))):
            with self.subTest(overrides=overrides):
                decision = decide("general", read(snap, claude(10, session_used=100)), settings(overrides), NOW)
                self.assertIsNone(decision["choice"])

    def test_a19_codex_session_exhausted_and_claude_week_exhausted(self):
        found = read(codex(10, session_used=100, credits=CREDITS_OK), claude(100))
        self.assertEqual(decide("general", found, settings(), NOW)["tier"], "credits")
        self.assertIsNone(decide("general", found, settings({"credits.openai-codex": False}), NOW)["choice"])

    def test_a20_claude_session_exhausted_and_codex_week_exhausted(self):
        found = read(codex(100, credits=CREDITS_OK), claude(10, session_used=100))
        decision = decide("general", found, settings(), NOW)
        self.assertEqual((decision["choice"], decision["tier"]), (CODEX, "credits"))
        anthropic = decide("general", found, settings({"credits.openai-codex": False, "credits.anthropic": True}), NOW)
        self.assertIsNone(anthropic["choice"])
        self.assertEqual(anthropic["eligibility"][CLAUDE]["credits_reason"], "credits_not_verifiable")

    def test_a21_week_only_on_both_sides_keeps_hysteresis(self):
        # Codex score 0.5/0.5 = 1.0; Claude 0.55/0.5 = 1.1 (exactly 10% more) and 0.56/0.5 = 1.12.
        kept = decide("general", read(codex(50, week_reset_h=84), claude(45, week_reset_h=84)), settings(), NOW, previous=CODEX)
        self.assertEqual((kept["choice"], kept["reason"]), (CODEX, "previous_preference_kept"))
        moved = decide("general", read(codex(50, week_reset_h=84), claude(44, week_reset_h=84)), settings(), NOW, previous=CODEX)
        self.assertEqual(moved["choice"], CLAUDE)

    def test_hysteresis_applies_inside_the_pressured_group(self):
        exact = read(codex(50, week_reset_h=84, session_used=96), claude(45, week_reset_h=84, session_used=96))
        kept = decide("general", exact, settings(), NOW, previous=CODEX)
        self.assertEqual((kept["choice"], kept["reason"]), (CODEX, "pressured_previous_preference_kept"))
        above = read(codex(50, week_reset_h=84, session_used=96), claude(44, week_reset_h=84, session_used=96))
        moved = decide("general", above, settings(), NOW, previous=CODEX)
        self.assertEqual((moved["choice"], moved["reason"]), (CLAUDE, "pressured_challenger_above_hysteresis"))

    def test_free_provider_wins_over_pressured_principal_in_the_conversation(self):
        decision = decide("conversation", read(codex(5, session_used=99), claude(90)), settings(), NOW, previous=CODEX)
        self.assertEqual((decision["choice"], decision["tier"]), (CLAUDE, "subscription"))

    def test_pressured_provider_outranks_paid_credits(self):
        found = read(codex(100, credits=CREDITS_OK), claude(90, session_used=99))
        decision = decide("general", found, settings(), NOW)
        self.assertEqual((decision["choice"], decision["tier"]), (CLAUDE, "subscription"))


class FallbackChainTests(unittest.TestCase):
    PAIR = {CODEX: {"model": "gpt-6.1-sol", "effort": "xhigh"}, CLAUDE: {"model": "claude-opus-5-5", "effort": "high"}}

    def chain(self, codex_snap, claude_snap, overrides=None):
        decision = decide("conversation", read(codex_snap, claude_snap), settings(overrides), NOW,
                          models={p: e["model"] for p, e in self.PAIR.items()})
        return decision, fallback_chain(decision, self.PAIR)

    def test_other_provider_enters_the_chain_when_free_or_pressured(self):
        for claude_snap in (claude(40), claude(40, session_used=97)):
            with self.subTest(claude=claude_snap.windows):
                decision, net = self.chain(codex(10), claude_snap)
                self.assertEqual(decision["choice"], CODEX)
                self.assertEqual(net["chain"], [{"provider": CODEX, "model": "gpt-6.1-sol"},
                                               {"provider": CLAUDE, "model": "claude-opus-5-5"}])

    def test_exhausted_peer_without_allowed_credits_is_left_out(self):
        decision, net = self.chain(codex(10), claude(100))
        self.assertEqual(net["chain"], [{"provider": CODEX, "model": "gpt-6.1-sol"}])
        self.assertEqual(net["excluded"], {CLAUDE: "exhausted_without_credits"})
        decision, net = self.chain(codex(100), claude(10))
        self.assertEqual(decision["choice"], CLAUDE)
        self.assertEqual(net["chain"], [{"provider": CLAUDE, "model": "claude-opus-5-5"}])

    def test_exhausted_peer_with_allowed_credits_stays_in_the_chain(self):
        decision, net = self.chain(codex(100, credits=CREDITS_OK), claude(10))
        self.assertEqual(decision["choice"], CLAUDE)
        self.assertEqual(net["chain"], [{"provider": CLAUDE, "model": "claude-opus-5-5"},
                                       {"provider": CODEX, "model": "gpt-6.1-sol"}])

    def test_unknown_peer_is_never_capacity(self):
        decision, net = self.chain(None, claude(10))
        self.assertEqual(decision["choice"], CLAUDE)
        self.assertEqual(net["chain"], [{"provider": CLAUDE, "model": "claude-opus-5-5"}])
        self.assertEqual(net["excluded"], {CODEX: "unknown"})

    def test_no_choice_has_no_chain(self):
        decision, net = self.chain(codex(100), claude(100))
        self.assertIsNone(decision["choice"])
        self.assertIsNone(net)

    def test_chain_entries_use_only_native_fields_and_never_credentials(self):
        _, net = self.chain(codex(10), claude(40))
        for entry in net["chain"]:
            self.assertEqual(set(entry), {"provider", "model"})


if __name__ == "__main__":
    unittest.main()
