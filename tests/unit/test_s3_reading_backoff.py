# README.md, HQR-35: failed reads back off without inventing quota or retaining private diagnostics.
"""Synthetic reader contracts, deterministic retry boundaries and Portuguese status output."""
from datetime import datetime, timedelta, timezone
import json
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from s2_fakes import NOW, claude, codex, reader_for
from test_s2_commands import Context, manager
from quota_router.readings import collect, native_importer, normalize
from quota_router.render import provider_line
from quota_router.settings import DEFAULTS


def imported_reader(fetch):
    """Only inert modules enter the native import seam; no real Hermes import or provider request."""
    agent = ModuleType("agent")
    account = ModuleType("agent.account_usage")
    setattr(account, "fetch_account_usage", fetch)
    setattr(agent, "account_usage", account)
    with patch.dict(sys.modules, {"agent": agent, "agent.account_usage": account}):
        reader = native_importer()
    if reader is None:
        raise AssertionError("Inert native reader was not imported")
    return reader


def reporting_reader(details):
    def fetch(provider, *, read_only=False, on_error=None):
        if not read_only:
            raise AssertionError("Native reads must stay read-only")
        if on_error is not None:
            on_error(details)
        return None
    return imported_reader(fetch)


def read_one(reader, now=NOW, cache=None, clock=None):
    found, queries = collect(("anthropic",), now, 60, reader=reader, cache=cache, clock=clock)
    return found["anthropic"], queries


class FailureBackoffTests(unittest.TestCase):
    def test_failed_fetch_is_not_requeried_inside_default_backoff(self):
        for value, reason in ((None, "no_snapshot"), (RuntimeError("synthetic-private-message"), "reader_error"),
                              (object(), "malformed_snapshot")):
            with self.subTest(reason=reason):
                cache = {}
                reader = reader_for(anthropic=value)
                first, issued = read_one(reader, cache=cache)
                again, repeated = read_one(reader, NOW + timedelta(seconds=299), cache)
                self.assertEqual((issued, repeated, len(getattr(reader, "calls"))), (1, 0, 1))
                self.assertEqual((first["state"], again["reason"]), ("unknown", reason))
                self.assertEqual(first["retry_at"], (NOW + timedelta(seconds=300)).isoformat())
                self.assertEqual(again["retry_at"], first["retry_at"])
                self.assertIn("anthropic", cache)
                self.assertNotIn("synthetic-private-message", json.dumps(cache))

    def test_failed_fetch_is_queried_again_at_exact_expiry(self):
        reader, cache = reader_for(anthropic=None), {}
        first, _ = read_one(reader, cache=cache)
        expired, issued = read_one(reader, NOW + timedelta(seconds=300), cache)
        self.assertEqual((issued, len(getattr(reader, "calls"))), (1, 2))
        self.assertEqual(first.get("retry_at"), (NOW + timedelta(seconds=300)).isoformat())
        self.assertEqual(expired.get("retry_at"), (NOW + timedelta(seconds=600)).isoformat())

    def test_failure_backoff_starts_after_fetch_including_exceptions(self):
        for value in (None, RuntimeError("synthetic")):
            with self.subTest(value=value):
                reader, cache = reader_for(anthropic=value), {}
                completed = NOW + timedelta(seconds=17)
                first, _ = read_one(reader, cache=cache, clock=lambda: completed)
                self.assertEqual(first.get("retry_at"), (completed + timedelta(seconds=300)).isoformat())
                _, issued = read_one(reader, NOW + timedelta(seconds=300), cache)
                self.assertEqual((issued, len(getattr(reader, "calls"))), (0, 1))

    def test_failure_backoff_is_independent_per_provider(self):
        reader = reader_for(openai_codex=codex(10), anthropic=None)
        cache = {}
        collect(("openai-codex", "anthropic"), NOW, 60, reader=reader, cache=cache)
        later = NOW + timedelta(seconds=61)
        found, issued = collect(("openai-codex", "anthropic"), later, 60, reader=reader, cache=cache)
        self.assertEqual((issued, getattr(reader, "calls").count("anthropic")), (1, 1))
        self.assertEqual(found["anthropic"]["reason"], "no_snapshot")

    def test_success_after_failure_replaces_failure_and_uses_normal_freshness(self):
        calls, cache = [], {}
        def reader(provider):
            calls.append(provider)
            return None if len(calls) == 1 else claude(10, fetched_at=NOW + timedelta(seconds=300))
        first, _ = read_one(reader, cache=cache)
        success, issued = read_one(reader, NOW + timedelta(seconds=300), cache)
        self.assertIn("retry_at", first)
        self.assertEqual((success["state"], issued), ("ok", 1))
        for key in ("retry_at", "retry_after_s", "failed_at"):
            self.assertNotIn(key, cache["anthropic"])
        reused, issued = read_one(reader, NOW + timedelta(seconds=330), cache)
        self.assertEqual((reused["state"], issued, len(calls)), ("ok", 0, 2))
        _, issued = read_one(reader, NOW + timedelta(seconds=361), cache)
        self.assertEqual((issued, len(calls)), (1, 3))

    def test_mode_change_clears_failure_backoff(self):
        reader = reader_for(openai_codex=None, anthropic=None)
        management, _, _ = manager(Context({"mode": "observe"}), reader)
        management.command("status --json")
        management.command("explain --json")
        self.assertEqual(len(getattr(reader, "calls")), 2)
        management.command("mode off --json")
        management.command("mode observe --json")
        self.assertEqual(len(getattr(reader, "calls")), 4)

    def test_missing_reader_does_not_cache_a_failed_fetch(self):
        cache = {}
        found, queries = collect(("anthropic",), NOW, 60, cache=cache, importer=lambda: None)
        self.assertEqual((found["anthropic"]["reason"], queries, cache), ("reader_unavailable", 0, {}))
        self.assertNotIn("retry_at", found["anthropic"])

    def test_retry_after_is_honored_and_clamped(self):
        for seconds, delay in ((90, 90), (90.5, 90.5), (0, 30), (-10, 30), (29, 30), (30, 30),
                               (300, 300), (3600, 3600), (7200, 3600), (10 ** 400, 3600)):
            with self.subTest(seconds=seconds):
                reader = reporting_reader({"kind": "http", "status": 429, "retry_after_s": seconds})
                cache = {}
                first, _ = read_one(reader, cache=cache)
                self.assertEqual(first.get("retry_at"), (NOW + timedelta(seconds=delay)).isoformat())
                again, issued = read_one(reader, NOW + timedelta(seconds=delay - 0.1), cache)
                self.assertEqual((issued, again["reason"]), (0, "http_429"))
                _, issued = read_one(reader, NOW + timedelta(seconds=delay), cache)
                self.assertEqual(issued, 1)

    def test_invalid_retry_after_uses_default_without_retaining_bad_value(self):
        for seconds in (True, "90", None, float("nan"), float("inf"), float("-inf"), {"private": "synthetic"}):
            with self.subTest(seconds=seconds):
                reader = reporting_reader({"kind": "http", "status": 429, "retry_after_s": seconds})
                found, _ = read_one(reader, cache={})
                self.assertEqual(found.get("retry_at"), (NOW + timedelta(seconds=300)).isoformat())
                self.assertNotIn("retry_after_s", found)
                json.dumps(found, allow_nan=False)


class NativeFailureReasonTests(unittest.TestCase):
    def test_old_reader_without_on_error_remains_no_snapshot(self):
        calls = []
        def old_reader(provider, *, read_only=False):
            calls.append((provider, read_only))
            return None
        reader = imported_reader(old_reader)
        self.assertEqual(calls, [])
        found, _ = read_one(reader)
        self.assertEqual((found["reason"], calls), ("no_snapshot", [("anthropic", True)]))

    def test_signature_detection_does_not_probe_reader_or_use_kwargs_as_support(self):
        calls = []
        def reader_with_kwargs(provider, *, read_only=False, **kwargs):
            calls.append((provider, read_only, kwargs))
        reader = imported_reader(reader_with_kwargs)
        self.assertEqual(calls, [])
        self.assertEqual(read_one(reader)[0]["reason"], "no_snapshot")
        self.assertEqual(calls, [("anthropic", True, {})])

    def test_uninspectable_old_reader_keeps_legacy_behavior(self):
        def fetch(provider, *, read_only=False):
            return None
        fetch.__signature__ = "not a signature"
        self.assertEqual(read_one(imported_reader(fetch))[0]["reason"], "no_snapshot")

    def test_new_native_reader_exposes_allowlisted_failure_reasons(self):
        cases = (({"kind": "http", "status": 429}, "http_429"), ({"kind": "http", "status": 401}, "http_401"),
                 ({"kind": "http", "status": 503}, "http_503"), ({"kind": "timeout"}, "timeout"),
                 ({"kind": "network"}, "network_error"), ({"kind": "error"}, "reader_error"))
        for details, reason in cases:
            with self.subTest(reason=reason):
                reader, cache = reporting_reader(details), {}
                outcome = reader("anthropic")
                self.assertEqual(normalize("anthropic", outcome, NOW, 60)["reason"], reason)
                found, queries = read_one(reader, cache=cache)
                self.assertEqual((found["state"], found["reason"], queries), ("unknown", reason, 1))
                repeated, queries = read_one(reader, NOW + timedelta(seconds=1), cache)
                self.assertEqual((repeated["reason"], queries), (reason, 0))

    def test_native_callback_extraneous_fields_are_never_retained(self):
        details = {"kind": "http", "status": 429, "retry_after_s": 75, "body": "synthetic-private-body",
                   "headers": {"Authorization": "synthetic-private-header"}, "token": "synthetic-private-token"}
        reader = reporting_reader(details)
        outcome = reader("anthropic")
        stored = repr(vars(outcome)) if hasattr(outcome, "__dict__") else repr(outcome)
        self.assertNotIn("synthetic-private", stored)
        cache = {}
        found, _ = read_one(reader, cache=cache)
        self.assertEqual(found["reason"], "http_429")
        self.assertEqual(found.get("retry_after_s"), 75)
        self.assertNotIn("synthetic-private", json.dumps([found, cache], allow_nan=False))
        self.assertNotIn("headers", json.dumps([found, cache]))

    def test_invalid_diagnostics_never_become_arbitrary_reason_or_status(self):
        cases = (None, [], {"kind": "synthetic-private-kind"}, {"kind": ["http"]},
                 *({"kind": "http", "status": status} for status in (True, "401", 429.0, {}, -1, 1000)))
        for details in cases:
            with self.subTest(details=details):
                found, _ = read_one(reporting_reader(details))
                self.assertEqual(found["reason"], "no_snapshot")
                self.assertNotIn("synthetic-private", json.dumps(found))

    def test_success_does_not_carry_callback_failure_or_leak_between_providers(self):
        calls = []
        def fetch(provider, *, read_only=False, on_error=None):
            calls.append(provider)
            if len(calls) == 1:
                if on_error:
                    on_error({"kind": "http", "status": 429})
                return None
            return claude(10) if len(calls) == 2 else None
        reader = imported_reader(fetch)
        self.assertEqual(read_one(reader)[0]["reason"], "http_429")
        success, _ = read_one(reader)
        self.assertEqual((success["state"], success["reason"]), ("ok", None))
        self.assertNotIn("retry_at", success)
        self.assertEqual(read_one(reader)[0]["reason"], "no_snapshot")


class FailureRenderTests(unittest.TestCase):
    def test_known_reasons_are_plain_portuguese_with_local_retry_time(self):
        retry_at = (NOW + timedelta(seconds=300)).isoformat()
        expected_time = datetime.fromisoformat(retry_at).astimezone().strftime("%H:%M")
        for reason, phrase in (("http_429", "a Anthropic limitou consultas (HTTP 429)"),
                               ("http_401", "login recusado (HTTP 401)"),
                               ("http_503", "a consulta falhou (HTTP 503)"),
                               ("timeout", "a consulta demorou demais"), ("network_error", "falha de rede")):
            with self.subTest(reason=reason):
                reading = {"state": "unknown", "reason": reason, "retry_at": retry_at}
                text = provider_line("anthropic", reading, DEFAULTS)
                self.assertIn(phrase, text)
                self.assertIn(f"nova tentativa às {expected_time}", text)
                self.assertNotIn("uma causa possível", text)
                self.assertNotIn(reason, text)

    def test_codex_rate_limit_does_not_blame_anthropic(self):
        text = provider_line("openai-codex", {"state": "unknown", "reason": "http_429"}, DEFAULTS)
        self.assertIn("o Codex limitou consultas (HTTP 429)", text)
        self.assertNotIn("Anthropic", text)

    def test_unknown_native_reason_keeps_existing_generic_text_and_retry(self):
        found, _ = read_one(reader_for(anthropic=None), cache={})
        text = provider_line("anthropic", found, DEFAULTS)
        self.assertIn("o provedor não respondeu, ou não há login", text)
        self.assertIn("uma causa possível é o limite de consultas", text)
        self.assertIn("nova tentativa às", text)

    def test_status_json_retains_reason_and_retry_without_granting_capacity(self):
        reader = reporting_reader({"kind": "http", "status": 429, "retry_after_s": 90})
        context = Context({"mode": "observe", "credits.anthropic": True, "credits.openai-codex": True})
        management, _, _ = manager(context, reader)
        first = json.loads(management.command("status --json"))
        status = json.loads(management.command("explain --json"))
        self.assertEqual((first["quota_queries"], status["quota_queries"]), (2, 2))
        found = status["quota"]["providers"]["anthropic"]
        self.assertEqual(found["reason"], "http_429")
        self.assertEqual(found.get("retry_at"), (NOW + timedelta(seconds=90)).isoformat())
        self.assertEqual(datetime.fromisoformat(found["retry_at"]).utcoffset(), timedelta(0))
        self.assertEqual(found["windows"], [])
        self.assertIsNone(status["decisions"]["conversation"]["choice"])
        self.assertTrue(status["decision_incomplete"])
        self.assertEqual(context.writes, [])


if __name__ == "__main__":
    unittest.main()
