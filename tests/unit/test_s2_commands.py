"""S2 commands over a synthetic plugin context (AC-03, AC-17, AC-24; scenarios D1, D5, D12)."""
import copy
from datetime import timedelta
import json
import unittest

from s2_fakes import NOW, claude, codex, reader_for
from test_s2_inventory import CONFIG, JOBS
from quota_router.lifecycle import Management


class Context:
    def __init__(self, settings=None):
        self.settings = dict(settings or {})
        self.writes = []

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def set_config(self, key, value):
        self.writes.append((key, value))
        self.settings[key] = value

    def __getattr__(self, name):
        raise AssertionError(f"Unexpected host capability: {name}")


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


def manager(ctx, reader=None, config=CONFIG, jobs=JOBS):
    clock = Clock()
    config_copy = copy.deepcopy(config)
    m = Management(ctx, importer=(lambda: reader) if reader else (lambda: None),
                   sources=lambda: (config_copy, copy.deepcopy(jobs)), clock=clock)
    return m, clock, config_copy


class CommandTests(unittest.TestCase):
    def test_off_reads_nothing(self):
        reader = reader_for(openai_codex=codex(10), anthropic=claude(10))
        m, _, _ = manager(Context(), reader)
        for command in ("status", "explain"):
            result = json.loads(m.command(command))
            self.assertEqual(result["quota"], {"state": "unknown", "source": None})
            self.assertEqual(result["quota_queries"], 0)
        self.assertEqual(reader.calls, [])

    def test_observe_reads_decides_and_writes_nothing_outside(self):
        reader = reader_for(openai_codex=codex(100), anthropic=claude(21))
        ctx = Context()
        m, clock, config = manager(ctx, reader)
        self.assertTrue(json.loads(m.command("mode observe"))["ok"])
        status = json.loads(m.command("status"))
        self.assertEqual(status["quota"]["state"], "observed")
        self.assertEqual(status["quota"]["providers"]["openai-codex"]["windows"][0]["used"], 1.0)
        self.assertEqual(status["quota_queries"], 2)
        explain = json.loads(m.command("explain"))
        self.assertEqual(explain["quota_queries"], 2)
        decisions = explain["decisions"]
        self.assertEqual(decisions["conversation"]["choice"], "anthropic")
        self.assertEqual(decisions["routes"]["deep"]["choice"], "anthropic")
        self.assertEqual(decisions["cron"]["state"], "blocked_partial_pins")
        self.assertEqual(explain["map"]["status"], "proposal_not_approved")
        self.assertFalse(explain["auto_available"])
        self.assertEqual(explain["extra_inferences"], 0)
        self.assertEqual(decisions["conversation"]["state"], "proposal_only")
        self.assertIsNone(decisions["conversation"]["would_change"])
        self.assertEqual(decisions["conversation"]["proposal_change"]["to"]["model"], "claude-opus-5-5")
        self.assertEqual(status["quota"]["source"], "injected_reader")
        summary = status["decisions"]
        self.assertEqual({k: summary["conversation"][k] for k in ("choice", "tier", "state")},
                         {"choice": "anthropic", "tier": "subscription", "state": "proposal_only"})
        self.assertIn("reason", summary["conversation"])
        self.assertEqual(summary["routes"]["general"]["choice"], "anthropic")
        self.assertEqual(status["settings"]["credits.anthropic"], False)
        self.assertIn("decided_at", status)
        self.assertIn("retries", status["coverage"]["not_governed"])
        self.assertEqual(status["profile"], "unknown")
        self.assertEqual(ctx.writes, [("mode", "observe")])
        self.assertEqual(config, CONFIG)
        clock.now = NOW + timedelta(seconds=61)
        self.assertEqual(json.loads(m.command("status"))["quota_queries"], 4)
        off = json.loads(m.command("mode off"))
        self.assertEqual((off["quota_queries"], off["quota_queries_total"]), (0, 4))
        self.assertEqual(json.loads(m.command("explain"))["quota_queries"], 0)
        self.assertEqual(len(reader.calls), 4)

    def test_config_show_set_reset_and_reject(self):
        ctx = Context()
        m, _, _ = manager(ctx)
        shown = json.loads(m.command("config"))
        self.assertFalse(shown["settings"]["credits.anthropic"])
        changed = json.loads(m.command("config set credits.anthropic on"))
        self.assertTrue(changed["ok"])
        self.assertTrue(ctx.settings["credits.anthropic"])
        for bad in ("config set limits.week_block_pct 500", "config set nope 1", "config set credits.anthropic",
                    "config set mode auto", "config reset nope"):
            before = list(ctx.writes)
            result = json.loads(m.command(bad))
            self.assertFalse(result["ok"], bad)
            self.assertEqual(ctx.writes, before, bad)
        reset = json.loads(m.command("config reset credits.anthropic"))
        self.assertTrue(reset["ok"])
        self.assertFalse(ctx.settings["credits.anthropic"])

    def test_invalid_saved_setting_marks_decision_incomplete(self):
        reader = reader_for(openai_codex=codex(10), anthropic=claude(10))
        ctx = Context({"mode": "observe", "limits.week_block_pct": 900})
        m, _, _ = manager(ctx, reader)
        result = json.loads(m.command("explain"))
        self.assertIn("limits.week_block_pct", result["settings_invalid"])
        self.assertTrue(result["decision_incomplete"])
        self.assertEqual(ctx.writes, [])

    def test_approved_map_makes_decisions_actionable(self):
        reader = reader_for(openai_codex=codex(100), anthropic=claude(21))
        ctx = Context({"mode": "observe"})
        m, _, _ = manager(ctx, reader)
        approved = json.loads(m.command("config approve-map base"))
        self.assertTrue(approved["ok"])
        roles = ctx.settings["roles"]
        self.assertEqual(roles["conversation"]["openai-codex"], {"model": "gpt-6.1-sol", "effort": "xhigh"})
        decision = json.loads(m.command("explain"))["decisions"]["conversation"]
        self.assertEqual(decision["state"], "decided")
        self.assertEqual(decision["would_change"]["to"]["provider"], "anthropic")
        self.assertFalse(json.loads(m.command("config approve-map nope"))["ok"])

    def sequence(self, ctx):
        """Manager whose reader serves the current `snaps` builders, fetched at the current clock time."""
        snaps = {}
        holder = {}

        def reader(provider):
            return snaps[provider](holder["clock"].now)

        m, clock, config = manager(ctx, reader)
        holder["clock"] = clock
        return m, clock, config, snaps

    def general(self, m):
        return json.loads(m.command("explain"))["decisions"]["routes"]["general"]

    def test_changing_readings_hysteresis_and_preference_revisions(self):
        m, clock, config, snaps = self.sequence(Context({"mode": "observe"}))
        snaps.update({"openai-codex": lambda t: codex(30, week_reset_h=84, fetched_at=t),
                      "anthropic": lambda t: claude(10, week_reset_h=84, fetched_at=t)})
        self.assertEqual(self.general(m)["choice"], "anthropic")
        clock.now += timedelta(seconds=120)
        snaps["openai-codex"] = lambda t: codex(10, week_reset_h=84, fetched_at=t)
        snaps["anthropic"] = lambda t: claude(15, week_reset_h=84, fetched_at=t)
        kept = self.general(m)
        self.assertEqual((kept["choice"], kept["reason"]), ("anthropic", "previous_preference_kept"))
        config["delegation"]["backends"]["model_map"]["options"][0]["model"] = "gpt-6.1-terra-mini"
        self.assertEqual(self.general(m)["choice"], "openai-codex")
        config["delegation"]["backends"]["model_map"]["options"][0]["model"] = "gpt-6.1-terra"
        self.assertEqual(self.general(m)["choice"], "anthropic")
        m.command("config set limits.reading_max_age_s 61")
        self.assertEqual(self.general(m)["choice"], "openai-codex")
        clock.now += timedelta(seconds=120)
        snaps["openai-codex"] = lambda t: codex(100, week_reset_h=84, fetched_at=t)
        changed = self.general(m)
        self.assertEqual((changed["choice"], changed["tier"]), ("anthropic", "subscription"))

    def test_idle_status_shows_age_and_refreshes(self):
        m, clock, _, snaps = self.sequence(Context({"mode": "observe"}))
        snaps.update({"openai-codex": lambda t: codex(10, fetched_at=t), "anthropic": lambda t: claude(10, fetched_at=t)})
        first = json.loads(m.command("status"))
        self.assertEqual(first["quota"]["providers"]["anthropic"]["age_s"], 0)
        self.assertEqual(first["decided_at"], NOW.isoformat())
        clock.now += timedelta(seconds=30)
        idle = json.loads(m.command("status"))
        self.assertEqual(idle["quota"]["providers"]["anthropic"]["age_s"], 30)
        self.assertEqual(idle["quota_queries"], first["quota_queries"])
        clock.now += timedelta(hours=2)
        later = json.loads(m.command("status"))
        self.assertEqual(later["quota"]["providers"]["anthropic"]["age_s"], 0)
        self.assertEqual(later["quota_queries"], first["quota_queries"] + 2)

    def test_reading_age_limit_setting(self):
        reader = reader_for(openai_codex=codex(10, fetched_at=NOW - timedelta(seconds=30)), anthropic=claude(10))
        m, _, _ = manager(Context({"mode": "observe", "limits.reading_max_age_s": 10}), reader)
        status = json.loads(m.command("status"))
        self.assertEqual(status["quota"]["providers"]["openai-codex"]["reason"], "stale_reading")
        self.assertTrue(status["decision_incomplete"])

    def test_approved_fable_and_astra_maps_stay_gated(self):
        reader = reader_for(openai_codex=codex(100), anthropic=claude(21))
        ctx = Context({"mode": "observe"})
        m, _, _ = manager(ctx, reader)
        self.assertTrue(json.loads(m.command("config approve-map fable"))["ok"])
        decisions = json.loads(m.command("explain"))["decisions"]
        self.assertIsNone(decisions["conversation"]["choice"])
        self.assertEqual(decisions["conversation"]["eligibility"]["anthropic"]["blocked_by"], "model_not_eligible:fable")
        self.assertEqual(decisions["routes"]["general"]["choice"], "anthropic")
        reader2 = reader_for(openai_codex=codex(10, astra=True), anthropic=claude(100))
        ctx2 = Context({"mode": "observe", "models.astra": True})
        m2, _, _ = manager(ctx2, reader2)
        self.assertTrue(json.loads(m2.command("config approve-map astra"))["ok"])
        deep = json.loads(m2.command("explain"))["decisions"]["routes"]["deep"]
        self.assertIsNone(deep["choice"])
        self.assertEqual(deep["eligibility"]["openai-codex"]["blocked_by"], "model_not_eligible:astra")
        self.assertIsNone(deep["would_change"])

    def test_status_explains_map_fallback_and_changes(self):
        reader = reader_for(openai_codex=codex(100), anthropic=claude(21))
        m, _, _ = manager(Context({"mode": "observe", "models.astra": True}), reader)
        status = json.loads(m.command("status"))
        self.assertEqual(status["decisions"]["variant"], "base")
        self.assertIn("astra_catalog_not_verifiable_by_plugin", status["decisions"]["map_notes"])
        self.assertEqual(status["decisions"]["map_status"], "proposal_not_approved")
        change = status["decisions"]["conversation"]["proposal_change"]
        self.assertEqual(change["to"], {"provider": "anthropic", "model": "claude-opus-5-5", "effort": "xhigh"})

    def test_invalid_approved_roles_are_ignored_and_reported(self):
        swapped = {"conversation": {"openai-codex": {"model": "claude-opus-5-5", "effort": "xhigh"},
                                    "anthropic": {"model": "claude-sonnet-5-5", "effort": "xhigh"}}}
        reader = reader_for(openai_codex=codex(10), anthropic=claude(10))
        m, _, _ = manager(Context({"mode": "observe", "roles": swapped}), reader)
        status = json.loads(m.command("explain"))
        self.assertIn("roles", status["settings_invalid"])
        self.assertTrue(status["decision_incomplete"])
        self.assertEqual(status["decisions"]["conversation"]["state"], "proposal_only")
        self.assertIsNone(status["decisions"]["conversation"]["would_change"])

    def test_inventory_delay_counts_toward_reading_age(self):
        reader = reader_for(openai_codex=codex(10, fetched_at=NOW - timedelta(seconds=57)),
                            anthropic=claude(10, fetched_at=NOW + timedelta(seconds=2)))
        clock = Clock()
        calls = []

        def sources():
            if not calls:
                clock.now += timedelta(seconds=4)
            calls.append(1)
            return copy.deepcopy(CONFIG), copy.deepcopy(JOBS)

        m = Management(Context({"mode": "observe"}), importer=lambda: reader, sources=sources, clock=clock)
        status = json.loads(m.command("status"))
        self.assertEqual(status["quota"]["providers"]["openai-codex"]["reason"], "stale_reading")
        self.assertEqual(status["decided_at"], (NOW + timedelta(seconds=4)).isoformat())

    def test_status_surface_reasons_pins_and_enrollment(self):
        reader = reader_for(openai_codex=codex(100), anthropic=claude(100))
        m, _, _ = manager(Context({"mode": "observe"}), reader)
        status = json.loads(m.command("status"))
        conversation = status["decisions"]["conversation"]
        self.assertEqual(conversation["reason"], "no_eligible_candidate")
        self.assertTrue(conversation["resets"])
        self.assertEqual(status["decisions"]["cron"]["partial_pins"],
                         [{"job": "c", "missing": ["provider"]}, {"job": "d1e2", "missing": ["provider", "model"]}])
        self.assertEqual(status["enrollment"]["state"], "enrolled")
        disabled = json.loads(manager(Context({"mode": "observe", "consumers.cron": False}), reader)[0].command("status"))
        self.assertEqual(disabled["decisions"]["cron"]["state"], "disabled_by_setting")

    def test_disabled_consumers_and_read_failure(self):
        reader = reader_for(openai_codex=codex(10), anthropic=claude(10))
        ctx = Context({"mode": "observe", "consumers.subagents": False, "consumers.conversation": False})
        m, _, _ = manager(ctx, reader)
        decisions = json.loads(m.command("explain"))["decisions"]
        self.assertEqual(decisions["conversation"]["state"], "disabled_by_setting")
        self.assertEqual(decisions["routes"]["deep"]["state"], "disabled_by_setting")

        class Failing(Context):
            def get_config(self, key, default=None):
                if key == "principal":
                    raise OSError("disk")
                return super().get_config(key, default)

        failing = Failing({"mode": "observe"})
        fm, _, _ = manager(failing, reader)
        status = json.loads(fm.command("status"))
        self.assertFalse(status["ok"])
        self.assertNotIn("disk", json.dumps(status))

    def test_output_is_strict_json(self):
        ctx = Context({"limits.hysteresis_pct": float("nan")})
        m, _, _ = manager(ctx)
        for command in ("status", "config", "explain"):
            json.loads(m.command(command), parse_constant=lambda token: self.fail(f"non-standard JSON {token}"))

    def test_auto_still_refused(self):
        ctx = Context()
        m, _, _ = manager(ctx)
        result = json.loads(m.command("mode auto"))
        self.assertFalse(result["ok"])
        self.assertEqual(ctx.writes, [])


if __name__ == "__main__":
    unittest.main()
