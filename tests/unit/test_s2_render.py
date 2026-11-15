"""Human-readable chat output (quota_router/render.py): conclusion first, no JSON or internal codes."""
import json
import re
import unittest

import copy
import os
import time
from unittest import mock

from datetime import timedelta

from s2_fakes import CREDITS_OK, NOW, WEEK, Snapshot, Window, claude, codex, codex_rate_limit, reader_for
from test_s2_commands import Context, manager
from quota_router.render import render
from quota_router.settings import DEFAULTS
from quota_router.render import SETTINGS_TEXT

CODES = re.compile(r"\b(proposal_only|no_snapshot|best_pacing|subscription|blocked_partial_pins|credits_available|"
                   r"previous_preference_kept|no_eligible_candidate|reading_unknown|disabled_by_setting)\b")


def payload(m, command):
    return json.loads(m.command(command + " --json"))


class RenderTests(unittest.TestCase):
    def observe(self, reader, **settings):
        m, _, _ = manager(Context(dict({"mode": "observe"}, **settings)), reader)
        return m

    def assert_human(self, text):
        self.assertFalse(text.lstrip().startswith("{"), text)
        self.assertIsNone(CODES.search(text), CODES.search(text))

    def test_status_leads_with_the_recommendation(self):
        m = self.observe(reader_for(openai_codex=codex(100), anthropic=claude(31)))
        text = render("status", payload(m, "status"))
        self.assert_human(text)
        lines = [l for l in text.splitlines() if l.strip()]
        self.assertIn("Observe", lines[0])
        self.assertTrue(lines[1].startswith("**Recomendação: Claude, pela franquia**"), lines[1])
        self.assertIn("a franquia semanal do Codex acabou", text)
        self.assertIn("approve-map base", text)
        self.assertIn("cron", text.lower())

    def test_no_candidate_and_unknown_readings_are_plain(self):
        m = self.observe(reader_for(openai_codex=None, anthropic=claude(100)))
        text = render("status", payload(m, "status"))
        self.assert_human(text)
        self.assertIn("Nenhum provedor pode ser usado agora", text)
        self.assertIn("sem dados do provedor", text)

    def test_off_explain_config_and_errors(self):
        m, _, _ = manager(Context(), reader_for())
        off = render("status", payload(m, "status"))
        self.assertIn("desligado (OFF)", off)
        self.assertIn("mode observe", off)
        refused = render("mode", payload(m, "mode auto"))
        self.assertTrue(refused.startswith("**Não foi possível:** O modo AUTO ainda não existe"), refused)
        self.assertNotIn("não conseguiu ler a própria configuração", refused)
        bad = render("config", payload(m, "config set limits.week_block_pct 250"))
        self.assertIn("Valor inválido para `limits.week_block_pct`", bad)
        config = render("config", payload(m, "config"))
        self.assert_human(config)
        for key in SETTINGS_TEXT:
            self.assertIn(f"`{key}`", config)
        self.assertEqual(set(SETTINGS_TEXT), set(DEFAULTS) - {"mode"})
        m2 = self.observe(reader_for(openai_codex=codex(100), anthropic=claude(31)))
        explain = render("explain", payload(m2, "explain"))
        self.assert_human(explain)
        self.assertIn("é o único com franquia livre", explain)
        self.assertEqual(explain.count("**Situação dos provedores**"), 1)

    def test_command_answers_in_text_by_default_and_json_on_request(self):
        m = self.observe(reader_for(openai_codex=codex(100), anthropic=claude(31)))
        for command in ("status", "explain", "config", "mode observe", "mode auto", "wat", "config set principal nobody"):
            text = m.command(command)
            self.assert_human(text)
            with self.assertRaises(ValueError):
                json.loads(text)
        self.assertEqual(json.loads(m.command("status --json"))["mode_effective"], "observe")
        self.assertEqual(json.loads(m.command("--json explain"))["decisions"]["conversation"]["choice"], "anthropic")
        self.assertTrue(m.command("wat").startswith("**Não foi possível:** Comando não reconhecido."))

    def test_attention_lists_pins_invalid_values_and_map_notes(self):
        m = self.observe(reader_for(openai_codex=codex(10, astra=True), anthropic=claude(10)),
                         **{"limits.week_block_pct": 250, "models.astra": True})
        text = render("status", payload(m, "status"))
        self.assert_human(text)
        self.assertIn("`limits.week_block_pct` tem um valor inválido", text)
        self.assertNotIn("250", text)
        self.assertIn("c (falta provedor); d1e2 (falta provedor e modelo)", text)
        self.assertIn("**Decisão incompleta:**", text)
        explain = render("explain", payload(m, "explain"))
        self.assertIn("Decisão incompleta", explain)
        self.assertIn("`limits.week_block_pct` tem um valor inválido", explain)
        self.assertNotIn("250", explain)
        self.assertIn("Astra fica de fora", text)


    def test_credits_follow_policy_limits_and_permission(self):
        cases = {
            "credits_ok": (codex(100, credits=CREDITS_OK), "Créditos disponíveis e permitidos"),
            "limit": (codex(100, credits=dict(CREDITS_OK, overage_limit_reached=True)), "limite de gastos foi atingido"),
            "spend": (codex(100, credits=CREDITS_OK, spend_reached=True), "limite de gastos foi atingido"),
            "unknown": (codex(100, credits=CREDITS_OK, spend_reached=None), "não puderam ser verificados"),
        }
        for name, (snap, expected) in cases.items():
            with self.subTest(name):
                text = render("status", payload(self.observe(reader_for(openai_codex=snap, anthropic=claude(100))), "status"))
                self.assertIn(expected, text)
                if name != "credits_ok":
                    self.assertNotIn("disponíveis e permitidos", text)
                    self.assertIn("Nenhum provedor pode ser usado agora", text)
        off = self.observe(reader_for(openai_codex=codex(100, credits=CREDITS_OK), anthropic=claude(100)),
                           **{"credits.openai-codex": False})
        self.assertIn("Há créditos, mas o uso está desligado", render("status", payload(off, "status")))

    def test_model_windows_and_configured_limits_are_named(self):
        m = self.observe(reader_for(openai_codex=codex(100), anthropic=claude(40, opus_used=100)))
        text = render("status", payload(m, "status"))
        self.assertIn("semana do Opus 100% usada (esgotada)", text)
        self.assertIn("a semana do Opus do Claude está esgotada", text)
        m = self.observe(reader_for(openai_codex=codex(85), anthropic=claude(10)), **{"limits.week_block_pct": 80})
        text = render("status", payload(m, "status"))
        self.assertIn("semana 85% usada (acima do limite configurado de 80%)", text)
        self.assertIn("passou do limite semanal configurado (80%)", text)
        self.assertNotIn("Codex acabou", text)
        explain = render("explain", payload(m, "explain"))
        self.assertIn("a cota semanal passou do limite configurado de 80%", explain)

    def test_unusable_readings_never_advertise_credits(self):
        far = Snapshot("openai-codex", "usage_api", NOW, (Window("Weekly", 100, NOW + timedelta(days=8)),),
                       raw={"credits": CREDITS_OK, "spend_control": {"reached": False}, "rate_limit": codex_rate_limit(WEEK)})
        cases = {"inconsistent": (far, "as datas da leitura não fecham"),
                 "denied": (codex(10, allowed=False, credits=CREDITS_OK), "o provedor nega o uso mas mostra franquia livre")}
        for name, (snap, reason) in cases.items():
            with self.subTest(name):
                result = payload(self.observe(reader_for(openai_codex=snap, anthropic=claude(100))), "status")
                text = render("status", result)
                self.assertIn(f"Leitura não confiável ({reason}): nem a franquia nem os créditos serão usados", text)
                self.assertIn(f"a leitura do Codex não é confiável ({reason})", text)
                self.assertNotIn("disponíveis e permitidos", text)
                self.assertIn("Nenhum provedor pode ser usado agora", text)

    def test_reading_source_is_named(self):
        text = render("status", payload(self.observe(reader_for(openai_codex=codex(10), anthropic=claude(10))), "status"))
        self.assertIn("**Cotas agora** (via leitor de teste (não é leitura real))", text)
        self.assertIn("(API de uso do Codex)", text)
        native = dict(payload(self.observe(reader_for(openai_codex=codex(10), anthropic=claude(10))), "status"))
        native["quota"] = dict(native["quota"], source="native_account_usage")
        self.assertIn("(via leitor de cotas do Hermes)", render("status", native))
        missing = payload(self.observe(reader_for(openai_codex=None, anthropic=claude(10))), "status")
        self.assertIn("sem dados do provedor", render("status", missing))

    def test_explain_names_the_model_window_that_blocks(self):
        m = self.observe(reader_for(openai_codex=codex(100), anthropic=claude(40, opus_used=100)))
        explain = render("explain", payload(m, "explain"))
        self.assertIn("a cota semanal do Opus acabou", explain)
        self.assertNotIn("**Claude**: a cota semanal acabou", explain)

    def test_hysteresis_uses_the_effective_setting(self):
        m = self.observe(reader_for(openai_codex=codex(10), anthropic=claude(10)), **{"limits.hysteresis_pct": 25})
        explain = render("explain", payload(m, "explain"))
        self.assertNotIn("10%", explain)
        self.assertIn("25%", explain)
        from quota_router.render import reason_text
        self.assertEqual(reason_text("previous_preference_kept", {"limits.hysteresis_pct": 7}),
                         "mantém a escolha anterior; o outro não superou o limite de troca de 7%")

    def test_partial_map_separates_approved_from_proposed(self):
        reader = reader_for(openai_codex=codex(100), anthropic=claude(21))
        ctx = Context({"mode": "observe"})
        m, _, _ = manager(ctx, reader)
        m.command("config approve-map base")
        roles = copy.deepcopy(ctx.settings["roles"])
        roles.pop("general")
        m2, _, _ = manager(Context({"mode": "observe", "roles": roles}), reader)
        result = payload(m2, "status")
        self.assertNotIn("roles", result.get("settings_invalid") or {})
        text = render("status", result)
        self.assertIn("**O que mudaria** (mapa aprovado)", text)
        self.assertIn("**O que mudaria** (proposta para os papéis ainda sem mapa aprovado)", text)
        proposed = text.split("proposta para os papéis ainda sem mapa aprovado)")[1].split("\n\n")[0]
        self.assertIn("general", proposed)
        explain = render("explain", payload(m2, "explain"))
        self.assertIn("**Mudanças por papel (mapa aprovado)**", explain)
        self.assertIn("**Mudanças por papel (proposta, ainda não aplicada)**", explain)

    def test_explain_lists_variant_mappings_and_status_shows_reading_age(self):
        m = self.observe(reader_for(openai_codex=codex(100), anthropic=claude(31)))
        explain = render("explain", payload(m, "explain"))
        self.assertIn("**Mapa base**", explain)
        self.assertRegex(explain, r"• general: Codex gpt-[^·]+ · Claude claude-")
        self.assertIn("• com Fable:", explain)
        self.assertIn("Lida há", render("status", payload(m, "status")))

    def test_inventory_unavailable_keeps_provider_level_recommendation(self):
        reader = reader_for(openai_codex=codex(100), anthropic=claude(31))
        m, _, _ = manager(Context({"mode": "observe"}), reader, config=None, jobs=None)
        result = payload(m, "status")
        self.assertEqual(result["decisions"]["state"], "inventory_unavailable")
        text = render("status", result)
        self.assertIn("Recomendação geral: Claude, pela franquia", text)

    def test_render_failure_falls_back_and_times_are_local(self):
        m = self.observe(reader_for(openai_codex=codex(100), anthropic=claude(31)))
        with mock.patch("quota_router.lifecycle.render", side_effect=KeyError("x")):
            self.assertIn("--json", m.command("status"))
        from quota_router.render import when
        old = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "America/Sao_Paulo"
            time.tzset()
            self.assertEqual(when("2026-11-18T11:08:00+00:00"), "qua 18/11 às 08:08")
        finally:
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
            time.tzset()


if __name__ == "__main__":
    unittest.main()
