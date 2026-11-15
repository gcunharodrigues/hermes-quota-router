"""S2 settings: schema, validation and invalid saved values (AC-24, scenarios D5 and D12)."""
import unittest

from quota_router.settings import DEFAULTS, load, validate


class SettingsTests(unittest.TestCase):
    def test_defaults_follow_owner_decisions(self):
        self.assertEqual(DEFAULTS["mode"], "off")
        self.assertTrue(DEFAULTS["credits.openai-codex"])
        self.assertFalse(DEFAULTS["credits.anthropic"])
        self.assertFalse(DEFAULTS["models.fable"])
        self.assertFalse(DEFAULTS["models.astra"])
        self.assertEqual(DEFAULTS["principal"], "openai-codex")
        self.assertEqual(DEFAULTS["conversation.policy"], "principal_first")
        self.assertTrue(DEFAULTS["consumers.conversation"])

    def test_validate_normalizes_and_rejects(self):
        self.assertEqual(validate("credits.anthropic", "on"), (True, True))
        self.assertEqual(validate("credits.anthropic", "off"), (True, False))
        self.assertEqual(validate("limits.hysteresis_pct", "10"), (True, 10))
        self.assertEqual(validate("limits.week_block_pct", 100), (True, 100))
        self.assertEqual(validate("principal", "anthropic"), (True, "anthropic"))
        for key, value in (("limits.week_block_pct", 0), ("limits.week_block_pct", 101), ("limits.hysteresis_pct", "x"),
                           ("limits.reading_max_age_s", True), ("credits.anthropic", "maybe"), ("principal", "openai"),
                           ("mode", "ON"), ("nope", 1), ("conversation.policy", None)):
            ok, reason = validate(key, value)
            self.assertFalse(ok, (key, value))
            self.assertIsInstance(reason, str)

    def test_invalid_saved_value_is_reported_and_replaced_by_default(self):
        saved = {"limits.week_block_pct": 250, "credits.anthropic": "sim", "principal": "anthropic"}
        effective, invalid = load(lambda key, default: saved.get(key, default))
        self.assertEqual(effective["limits.week_block_pct"], 100)
        self.assertFalse(effective["credits.anthropic"])
        self.assertEqual(effective["principal"], "anthropic")
        self.assertEqual(set(invalid), {"limits.week_block_pct", "credits.anthropic"})
        self.assertEqual(invalid["limits.week_block_pct"]["saved_type"], "int")
        self.assertNotIn("saved", invalid["credits.anthropic"])

    def test_invalid_values_are_never_echoed(self):
        secret = "sk-live-secret-value user@example.com https://example.invalid"
        effective, invalid = load(lambda key, default: {"principal": secret, "limits.hysteresis_pct": float("nan")}.get(key, default))
        self.assertNotIn("secret", repr(invalid))
        self.assertNotIn("example", repr(invalid))
        self.assertEqual(invalid["principal"]["saved_type"], "str")
        self.assertEqual(effective["principal"], "openai-codex")

    def test_roles_reject_models_under_the_wrong_provider(self):
        swapped = {"deep": {"openai-codex": {"model": "claude-opus-5-5", "effort": "xhigh"},
                            "anthropic": {"model": "claude-sonnet-5-5", "effort": "xhigh"}}}
        self.assertFalse(validate("roles", swapped)[0])
        backwards = {"deep": {"openai-codex": {"model": "gpt-6.1-sol", "effort": "xhigh"},
                              "anthropic": {"model": "gpt-6.1-terra", "effort": "xhigh"}}}
        self.assertFalse(validate("roles", backwards)[0])

    def test_roles_map_validation(self):
        good = {"deep": {"openai-codex": {"model": "gpt-6.1-sol", "effort": "xhigh"},
                         "anthropic": {"model": "claude-opus-5-5", "effort": "xhigh"}}}
        self.assertEqual(validate("roles", good), (True, good))
        self.assertEqual(DEFAULTS["roles"], {})
        for bad in ({"deep": {"openai-codex": {"model": "x"}}}, {"de ep": good["deep"]}, ["deep"],
                    {"deep": {"openai-codex": {"model": "bad model", "effort": "xhigh"}, "anthropic": good["deep"]["anthropic"]}}):
            self.assertFalse(validate("roles", bad)[0], bad)


if __name__ == "__main__":
    unittest.main()
