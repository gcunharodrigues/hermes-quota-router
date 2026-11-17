"""HQR-38 plain Portuguese states and safety net in Observe output (decisions/hqr-38-spec.md, "Regras de decisão")."""
import json
import unittest

from datetime import timedelta

from s2_fakes import CREDITS_OK, NOW, WEEK, Snapshot, Window, claude, codex, codex_rate_limit, reader_for
from test_s2_commands import Context, manager
from quota_router.render import render


def observe(reader, **settings):
    m, _, _ = manager(Context(dict({"mode": "observe"}, **settings)), reader)
    return m


class StateTextTests(unittest.TestCase):
    def test_status_names_each_provider_state(self):
        m = observe(reader_for(openai_codex=codex(10, session_used=97), anthropic=claude(100)))
        payload = json.loads(m.command("status --json"))
        self.assertEqual(payload["quota"]["states"], {"openai-codex": "pressured", "anthropic": "exhausted"})
        text = render("status", payload)
        self.assertIn("Codex: Pressionado", text)
        self.assertIn("Claude: Esgotado", text)
        unknown = render("status", json.loads(observe(reader_for(openai_codex=None, anthropic=claude(10))).command("status --json")))
        self.assertIn("Codex: Desconhecido", unknown)
        self.assertIn("Claude: Livre", unknown)

    def test_pressured_choice_and_safety_net_are_explained(self):
        m = observe(reader_for(openai_codex=codex(20, session_used=96, credits=CREDITS_OK), anthropic=claude(50, session_used=97)))
        text = render("explain", json.loads(m.command("explain --json")))
        self.assertIn("Pressionado", text)
        self.assertIn("as duas janelas de 5 h passaram de 95%", text)
        self.assertNotIn("com créditos", text)

    def test_safety_net_lines_name_the_peer_or_its_absence(self):
        m = observe(reader_for(openai_codex=codex(10), anthropic=claude(100)))
        text = render("status", json.loads(m.command("status --json")))
        self.assertIn("Rede de segurança", text)
        self.assertIn("sem rede de segurança", text)

    def test_inconsistent_window_keeps_verified_credits_visible(self):
        # decisions/hqr-38-spec.md, A23: the subscription is unreliable, the credit verdict still follows the credit evidence.
        far = Snapshot("openai-codex", "usage_api", NOW, (Window("Weekly", 100, NOW + timedelta(days=8)),),
                       raw={"credits": CREDITS_OK, "spend_control": {"reached": False}, "rate_limit": codex_rate_limit(WEEK)})
        text = render("status", json.loads(observe(reader_for(openai_codex=far, anthropic=claude(100))).command("status --json")))
        self.assertIn("Leitura não confiável (as datas da leitura não fecham): a franquia não será usada", text)
        self.assertIn("Créditos disponíveis e permitidos", text)
        self.assertIn("**Recomendação: Codex, com créditos**", text)


if __name__ == "__main__":
    unittest.main()
