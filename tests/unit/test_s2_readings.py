"""S2 native readings: normalization, unknown states, credit allowlist and cache (AC-16, scenarios A7-A9, A15, B4, B5)."""
from datetime import timedelta
import unittest

from s2_fakes import CREDITS_OK, NOW, WEEK, Snapshot, Window, claude, codex, codex_rate_limit, reader_for
from quota_router.readings import collect, normalize


class NormalizeTests(unittest.TestCase):
    def test_codex_windows_credits_and_astra_from_allowlist(self):
        raw_credits = dict(CREDITS_OK, secret_note="never copied")
        reading = normalize("openai-codex", codex(100, session_used=10, credits=raw_credits, astra=True), NOW, 60)
        self.assertEqual(reading["state"], "ok")
        kinds = {w["kind"]: w for w in reading["windows"]}
        self.assertEqual(kinds["week"]["used"], 1.0)
        self.assertEqual(kinds["week"]["duration_s"], 604800)
        self.assertEqual(kinds["session"]["used"], 0.1)
        self.assertEqual(reading["credits"], {"visible": True, "has_credits": True, "unlimited": False, "balance_positive": True,
                                              "overage_limit_reached": False, "spend_reached": False})
        self.assertTrue(reading["astra_available"])
        self.assertNotIn("secret_note", repr(reading))
        self.assertNotIn("12.50", repr(reading))

    def test_anthropic_credit_state_is_not_visible(self):
        reading = normalize("anthropic", claude(21, opus_used=30), NOW, 60)
        self.assertEqual(reading["state"], "ok")
        self.assertEqual(reading["credits"], {"visible": False})
        self.assertIsNone(reading["astra_available"])
        model = [w for w in reading["windows"] if w["kind"] == "model_week"]
        self.assertEqual(model[0]["family"], "opus")

    def test_unknown_states(self):
        cases = {
            "no_snapshot": None,
            "provider_unavailable": Snapshot("anthropic", "x", NOW, unavailable_reason="not oauth"),
            "stale_reading": claude(10, fetched_at=NOW - timedelta(seconds=61)),
            "future_reading": claude(10, fetched_at=NOW + timedelta(seconds=1)),
            "invalid_timestamp": claude(10, fetched_at=NOW.replace(tzinfo=None)),
            "provider_mismatch": codex(10),
            "unknown_window_label": Snapshot("anthropic", "x", NOW, (Window("Current week", 10, NOW + timedelta(days=1)),
                                                                     Window("Weekly Fable", 10, NOW + timedelta(days=1)))),
            "conflicting_windows": Snapshot("anthropic", "x", NOW, (Window("Current week", 10, NOW + timedelta(days=1)),
                                                                    Window("Current week", 30, NOW + timedelta(days=1)))),
            "malformed_snapshot": Snapshot("anthropic", "x", NOW, windows=7),
            # decisions/hqr-38-spec.md, A32: above 100% is clamped; a negative value is still malformed.
            "malformed_window": Snapshot("anthropic", "x", NOW, (Window("Current week", -5, NOW + timedelta(days=1)),)),
            "reset_passed": Snapshot("anthropic", "x", NOW, (Window("Current week", 10, NOW),)),
            "no_week_window": Snapshot("anthropic", "x", NOW, (Window("Current session", 10, NOW + timedelta(hours=1)),)),
        }
        for reason, snap in cases.items():
            reading = normalize("anthropic", snap, NOW, 60)
            self.assertEqual((reading["state"], reading["reason"]), ("unknown", reason), reason)
        edge = normalize("anthropic", claude(10, fetched_at=NOW - timedelta(seconds=60)), NOW, 60)
        self.assertEqual(edge["state"], "ok")
        self.assertEqual(edge["source"], "oauth_usage_api")
        self.assertEqual(normalize("anthropic", object(), NOW, 60)["reason"], "malformed_snapshot")


class CollectTests(unittest.TestCase):
    def test_reader_unavailable_emits_no_query(self):
        readings, queries = collect(("openai-codex", "anthropic"), NOW, 60, reader=None, importer=lambda: None)
        self.assertEqual(queries, 0)
        self.assertEqual({r["reason"] for r in readings.values()}, {"reader_unavailable"})

    def test_reader_error_counts_attempt_and_stays_unknown(self):
        reader = reader_for(openai_codex=RuntimeError("boom"), anthropic=claude(10))
        readings, queries = collect(("openai-codex", "anthropic"), NOW, 60, reader=reader)
        self.assertEqual(queries, 2)
        self.assertEqual(readings["openai-codex"]["reason"], "reader_error")
        self.assertNotIn("boom", repr(readings))
        self.assertEqual(readings["anthropic"]["state"], "ok")

    def test_codex_window_duration_must_be_published(self):
        reset = NOW + timedelta(days=1)
        for rate_limit in (codex_rate_limit(86400), {}, codex_rate_limit("604800"), codex_rate_limit(True)):
            snapshot = Snapshot("openai-codex", "usage_api", NOW, (Window("Weekly", 10, reset),), raw={"rate_limit": rate_limit})
            self.assertEqual(normalize("openai-codex", snapshot, NOW, 60)["reason"], "window_duration_unqualified", rate_limit)
        ok = Snapshot("openai-codex", "usage_api", NOW, (Window("Weekly", 10, reset),), raw={"rate_limit": codex_rate_limit(WEEK)})
        self.assertEqual(normalize("openai-codex", ok, NOW, 60)["state"], "ok")

    def test_codex_duration_evidence_is_bound_to_its_own_window(self):
        reset = NOW + timedelta(days=1)
        # Host skipped a primary window without usage and labeled the secondary one positionally.
        borrowed = Snapshot("openai-codex", "usage_api", NOW, (Window("Weekly", 10, reset),),
                            raw={"rate_limit": codex_rate_limit(WEEK, 86400)})
        self.assertEqual(normalize("openai-codex", borrowed, NOW, 60)["reason"], "window_duration_unqualified")
        swapped = Snapshot("openai-codex", "usage_api", NOW,
                           (Window("Session", 10, NOW + timedelta(hours=2)), Window("Weekly", 10, reset)),
                           raw={"rate_limit": codex_rate_limit(WEEK, 18000)})
        self.assertEqual(normalize("openai-codex", swapped, NOW, 60)["reason"], "window_duration_unqualified")
        both = Snapshot("openai-codex", "usage_api", NOW,
                        (Window("Session", 10, NOW + timedelta(hours=2)), Window("Weekly", 10, reset)),
                        raw={"rate_limit": codex_rate_limit(18000, WEEK)})
        self.assertEqual(normalize("openai-codex", both, NOW, 60)["state"], "ok")

    def test_window_scope_must_match_label(self):
        reset = NOW + timedelta(days=1)
        cases = (Snapshot("anthropic", "x", NOW, (Window("Current week", 10, reset), Window("Opus week", 10, reset, scope="account"))),
                 Snapshot("anthropic", "x", NOW, (Window("Current week", 10, reset, scope="model"),)))
        for snapshot in cases:
            self.assertEqual(normalize("anthropic", snapshot, NOW, 60)["reason"], "scope_mismatch")

    def test_readings_are_revalidated_at_decision_time(self):
        cache = {}
        aging = codex(10, fetched_at=NOW - timedelta(seconds=59))
        reader = reader_for(openai_codex=aging, anthropic=claude(10, fetched_at=NOW + timedelta(seconds=2)))
        collect(("openai-codex",), NOW, 60, reader=reader, cache=cache)
        found, _ = collect(("openai-codex", "anthropic"), NOW, 60, reader=reader, cache=cache,
                           clock=lambda: NOW + timedelta(seconds=2))
        self.assertEqual(found["openai-codex"]["reason"], "stale_reading")
        self.assertEqual(found["anthropic"]["state"], "ok")
        soon = Snapshot("openai-codex", "usage_api", NOW, (Window("Weekly", 10, NOW + timedelta(seconds=1)),),
                        raw={"rate_limit": codex_rate_limit(WEEK)})
        crossed, _ = collect(("openai-codex",), NOW, 60, reader=reader_for(openai_codex=soon),
                             clock=lambda: NOW + timedelta(seconds=2))
        self.assertEqual(crossed["openai-codex"]["reason"], "reset_passed")

    def test_age_uses_clock_after_fetch(self):
        reader = reader_for(openai_codex=codex(10, fetched_at=NOW + timedelta(seconds=3)), anthropic=claude(10))
        readings, _ = collect(("openai-codex",), NOW, 60, reader=reader, clock=lambda: NOW + timedelta(seconds=3))
        self.assertEqual(readings["openai-codex"]["state"], "ok")

    def test_cache_refetches_after_reset_and_reports_current_age(self):
        soon = Snapshot("anthropic", "oauth_usage_api", NOW, (Window("Current week", 10, NOW + timedelta(seconds=1)),))
        reader = reader_for(anthropic=soon)
        cache = {}
        collect(("anthropic",), NOW, 60, reader=reader, cache=cache)
        later, queries = collect(("anthropic",), NOW + timedelta(seconds=2), 60, reader=reader, cache=cache)
        self.assertEqual(queries, 1)
        self.assertEqual(later["anthropic"]["reason"], "reset_passed")
        reader2 = reader_for(anthropic=claude(10))
        cache2 = {}
        collect(("anthropic",), NOW, 60, reader=reader2, cache=cache2)
        aged, queries2 = collect(("anthropic",), NOW + timedelta(seconds=30), 60, reader=reader2, cache=cache2)
        self.assertEqual(queries2, 0)
        self.assertEqual(aged["anthropic"]["age_s"], 30)

    def test_cache_reuses_fresh_reading(self):
        reader = reader_for(openai_codex=codex(10), anthropic=claude(10))
        cache = {}
        collect(("openai-codex", "anthropic"), NOW, 60, reader=reader, cache=cache)
        _, queries = collect(("openai-codex", "anthropic"), NOW + timedelta(seconds=30), 60, reader=reader, cache=cache)
        self.assertEqual(queries, 0)
        self.assertEqual(len(reader.calls), 2)


if __name__ == "__main__":
    unittest.main()
