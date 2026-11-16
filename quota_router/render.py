"""Human-readable chat output for /quota-router (Portuguese); raw JSON stays available with `--json`.

Order follows the owner-brief rules: conclusion first, then the numbers behind it, then what needs attention,
then how to act; technical limits last. Internal codes never reach the text: each one maps to a plain sentence.
"""
from datetime import datetime
import re

from .policy import eligibility
from .settings import DEFAULTS

NAMES = {"openai-codex": "Codex", "anthropic": "Claude"}
WEEKDAYS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")

READING_REASONS = {
    "no_snapshot": "sem dados do provedor (sem login, ou o provedor não respondeu)",
    "reader_unavailable": "o leitor de cotas do Hermes não está disponível",
    "reader_error": "a consulta ao provedor falhou",
    "provider_unavailable": "o provedor informou que a leitura está indisponível",
    "provider_mismatch": "a leitura veio de outro provedor",
    "invalid_timestamp": "a leitura veio sem horário confiável",
    "future_reading": "a leitura veio com horário no futuro",
    "stale_reading": "a leitura ficou velha antes da decisão",
    "reset_passed": "a cota acabou de renovar; a próxima consulta traz o valor novo",
    "unknown_window_label": "o provedor mudou o formato da leitura",
    "scope_mismatch": "o provedor mudou o formato da leitura",
    "conflicting_windows": "a leitura veio com janelas repetidas",
    "malformed_window": "a leitura veio com números inválidos",
    "malformed_snapshot": "a leitura veio em formato inesperado",
    "no_week_window": "a leitura não trouxe a cota semanal",
    "window_duration_unqualified": "o Codex não confirmou a duração das janelas",
}

BLOCKS = {
    "week": "a franquia semanal acabou",
    "session": "a janela de 5 h está no limite",
    "inconsistent_window": "as datas da leitura não fecham",
    "upstream_denied_contradiction": "o provedor nega o uso mas mostra franquia livre",
    "no_week_window": "a leitura não trouxe a cota semanal",
    "model_not_eligible:fable": "o modelo Fable não pode ser verificado",
    "model_not_eligible:astra": "o modelo Astra não pode ser verificado",
}

CREDITS = {
    "credits_available": "créditos disponíveis",
    "credits_disabled": "uso de créditos desligado",
    "credits_not_verifiable": "créditos não verificáveis",
    "credits_limit_reached": "limite de créditos atingido",
    "credits_limits_not_verifiable": "limites de créditos não verificáveis",
    "credits_empty": "sem saldo de créditos",
    "reading_inconsistent": "leitura inconsistente",
    "reading_unknown": "leitura desconhecida",
    "model_not_eligible": "modelo não verificável",
}

DECISION_REASONS = {
    "principal_eligible": "o provedor principal tem franquia",
    "best_pacing": "tem a maior folga de franquia para o tempo que falta",
    "previous_preference_kept": "mantém a escolha anterior; o outro não superou o limite de troca de {h}%",
    "challenger_above_hysteresis": "passou a ter mais de {h}% de vantagem, o limite de troca",
    "credits_after_subscriptions": "nenhuma franquia serve; usa créditos permitidos",
    "no_eligible_candidate": "nenhum provedor pode ser usado agora",
    "only_subscription": "é o único com franquia livre; créditos só entram quando nenhuma franquia serve",
}

MAP_NOTES = {
    "fable_window_not_visible": "Fable fica de fora: a cota própria dele não chega ao plugin.",
    "astra_catalog_not_verifiable_by_plugin": "Astra fica de fora: o catálogo da conta só é visível com o token, que o plugin não usa.",
    "astra_unavailable": "Astra não aparece disponível na leitura do Codex.",
}

SETTINGS_TEXT = {
    "consumers.conversation": ("O que recomendar", "recomendar o modelo da conversa principal (vale em sessões novas)"),
    "consumers.subagents": ("O que recomendar", "recomendar o modelo de cada rota de subagente"),
    "consumers.cron": ("O que recomendar", "recomendar o modelo dos jobs agendados"),
    "conversation.policy": ("Conversa", "como escolher na conversa: principal_first fica no principal enquanto ele tiver franquia; pacing usa quem tiver mais folga"),
    "principal": ("Geral", "provedor preferido na conversa e no desempate"),
    "credits.openai-codex": ("Créditos", "usar créditos do Codex quando nenhuma franquia servir"),
    "credits.anthropic": ("Créditos", "usar créditos da Anthropic quando nenhuma franquia servir"),
    "credits.order": ("Créditos", "créditos só depois das franquias"),
    "models.fable": ("Modelos", "incluir o Fable nos candidatos"),
    "models.astra": ("Modelos", "incluir o Astra nos candidatos"),
    "limits.session_block_pct": ("Limites", "bloquear um provedor quando a janela de 5 h passar deste uso (%)"),
    "limits.week_block_pct": ("Limites", "bloquear um provedor quando a semana passar deste uso (%)"),
    "limits.reading_max_age_s": ("Limites", "idade máxima de uma leitura de cota (segundos)"),
    "limits.hysteresis_pct": ("Limites", "vantagem mínima para trocar de provedor (%)"),
    "roles": ("Mapa", "mapa de modelos aprovado por papel"),
}

ERRORS = (
    (r"^AUTO unavailable", "O modo AUTO ainda não existe: nesta versão o plugin só observa e recomenda. Nada foi gravado."),
    (r"^Usage:", "Comando não reconhecido."),
    (r"^Use /quota-router mode", "Para mudar o modo, use `/quota-router mode off` ou `/quota-router mode observe`."),
    (r"^Invalid value for ([\w.-]+)", r"Valor inválido para `\1`. Nada foi gravado."),
    (r"^Unknown map variant", "Variante de mapa desconhecida, ou o inventário do profile não pôde ser lido. Nada foi gravado."),
    (r"^Proposed map is invalid", "O mapa proposto não passou na validação. Nada foi gravado."),
    (r"^Native plugin settings write failed", "O Hermes não conseguiu gravar a configuração. Nada mudou."),
    (r"^Plugin instance unloaded", "O plugin foi descarregado. Reinicie o Hermes para usá-lo de novo."),
    (r"non-finite number", "O resultado tinha um número inválido e não foi exibido."),
)


def when(value, with_weekday=True):
    """`qui 18/11 às 11:08` in the host's local time."""
    try:
        moment = datetime.fromisoformat(value).astimezone()
    except (TypeError, ValueError):
        return "data desconhecida"
    day = f"{WEEKDAYS[moment.weekday()]} " if with_weekday else ""
    return f"{day}{moment:%d/%m} às {moment:%H:%M}"


def first_upper(text):
    """Capitalize the first letter only; str.capitalize would lower-case names such as Hermes or Claude."""
    return text[:1].upper() + text[1:]


def pct(value):
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") + "%"


def route(target):
    if not target:
        return "sem rota definida"
    effort = f" {target['effort']}" if target.get("effort") else ""
    return f"{target.get('model') or 'modelo herdado'}{effort}"


def error_text(error):
    for pattern, text in ERRORS:
        if re.search(pattern, error or ""):
            return re.sub(pattern + r".*", text, error, count=1, flags=re.S) if "\\1" in text else text
    return "Não foi possível concluir o comando."


MISSING = {"provider": "provedor", "model": "modelo"}
FAMILIES = {"opus": "Opus", "sonnet": "Sonnet"}


def reason_text(reason, settings):
    return DECISION_REASONS.get(reason, "motivo não informado").format(h=settings.get("limits.hysteresis_pct", 10))


def limit_of(window, settings):
    return settings["limits.session_block_pct"] if window["kind"] == "session" else settings["limits.week_block_pct"]


def over(window, settings):
    """`None` when the window is under its limit; otherwise how it is blocked, in words."""
    limit = limit_of(window, settings)
    if window["used_pct"] < limit:
        return None
    return "esgotada" if limit >= 100 else f"acima do limite configurado de {limit}%"


SOURCES = {"usage_api": "API de uso do Codex", "oauth_usage_api": "API de uso da Anthropic"}
QUOTA_SOURCES = {"native_account_usage": "leitor de cotas do Hermes", "injected_reader": "leitor de teste (não é leitura real)"}
UNUSABLE = ("inconsistent_window", "upstream_denied_contradiction", "no_week_window")


def block_text(blocked, settings, window=None):
    if blocked == "week":
        limit = settings["limits.week_block_pct"]
        family = (window or {}).get("family") if (window or {}).get("kind") == "model_week" else None
        what = f"a cota semanal do {FAMILIES.get(family, family)}" if family else "a cota semanal"
        return f"{what} acabou" if limit >= 100 else f"{what} passou do limite configurado de {limit}%"
    if blocked == "session":
        return f"a janela de 5 h passou do limite configurado de {settings['limits.session_block_pct']}%"
    if blocked.startswith("unknown:"):
        return READING_REASONS.get(blocked.split(":", 1)[1], "leitura indisponível")
    return BLOCKS.get(blocked, "fora da franquia")


def window_name(window):
    if window["kind"] == "session":
        return "janela de 5 h"
    if window["kind"] == "model_week":
        return f"semana do {FAMILIES.get(window['family'], window['family'] or 'modelo')}"
    return "semana"


def credit_text(provider, reading, settings):
    """Mirror of policy._credits: balance, limits and permission, in that order."""
    allowed = settings.get(f"credits.{provider}")
    credits = reading.get("credits") or {}
    if not credits.get("visible"):
        hidden = f"o Hermes não informa ao plugin os créditos do {NAMES[provider]}"
        return hidden + ("; uso de créditos desligado nas configurações" if not allowed else "; créditos não serão usados")
    limits = (credits.get("overage_limit_reached"), credits.get("spend_reached"))
    funded = credits.get("has_credits") is True and credits.get("balance_positive") is True
    if True in limits:
        return "há saldo, mas o limite de gastos foi atingido; créditos não serão usados" if funded else "limite de gastos atingido"
    if limits != (False, False):
        return "os limites de gastos não puderam ser verificados; créditos não serão usados"
    if not funded:
        return "sem saldo de créditos"
    return "créditos disponíveis e permitidos, só depois das franquias" if allowed else "há créditos, mas o uso está desligado"


def account_block(reading, settings, decided_at):
    """Account-level policy verdict (no model windows) when it makes both tiers unusable; None otherwise."""
    try:
        verdict = eligibility(reading, settings, datetime.fromisoformat(decided_at))
    except (TypeError, ValueError, KeyError):
        return None
    return verdict["blocked_by"] if verdict.get("blocked_by") in UNUSABLE else None


def provider_line(provider, reading, settings, decided_at=None):
    name = NAMES[provider]
    if reading["state"] != "ok":
        return f"• **{name}**: leitura indisponível ({READING_REASONS.get(reading['reason'], 'leitura não confiável')})."
    parts = []
    order = {"week": 0, "session": 1, "model_week": 2}
    for window in sorted(reading["windows"], key=lambda w: order[w["kind"]]):
        state = over(window, settings)
        tail = f" ({state})" if state else ""
        parts.append(f"{window_name(window)} {pct(window['used_pct'])} usada{tail}, renova {when(window['reset_at'])}")
    kinds = {w["kind"] for w in reading["windows"]}
    if provider == "anthropic" and "week" in kinds and not kinds & {"session", "model_week"}:
        parts.append("a Anthropic não informa janela de 5 h nem cota própria do Opus, que usa esta cota semanal")
    unusable = account_block(reading, settings, decided_at)
    if unusable:
        credit = f"Leitura não confiável ({BLOCKS[unusable]}): nem a franquia nem os créditos serão usados"
    else:
        credit = first_upper(credit_text(provider, reading, settings))
    age = reading.get("age_s")
    origin = SOURCES.get(reading.get("source"), "fonte não identificada")
    read = f" Lida há {int(age)} s ({origin})." if isinstance(age, (int, float)) else f" Fonte: {origin}."
    return f"• **{name}**: {'; '.join(parts)}. {credit}.{read}"


def consumers(decisions):
    """(label, decision) pairs in reading order."""
    items = [("a conversa", decisions["conversation"])]
    items += [(f"a rota {name}", d) for name, d in sorted(decisions.get("routes", {}).items())]
    items.append(("o cron", decisions["cron"]))
    return items


def recommendation(decisions, providers, settings, decided_at=None):
    groups = {}
    for label, decision in consumers(decisions):
        if decision.get("state") in ("disabled_by_setting", "blocked_partial_pins", "jobs_unavailable"):
            continue
        groups.setdefault((decision.get("choice"), decision.get("tier")), []).append(label)
    lines = []
    routes = len(decisions.get("routes", {}))
    for (choice, tier), labels in groups.items():
        who = describe_scope(labels, routes)
        if choice is None:
            resets = sorted(r for _, d in consumers(decisions) for r in (d.get("resets") or []))
            back = f" A primeira franquia renova {when(resets[0])}." if resets else ""
            lines.append(f"**Nenhum provedor pode ser usado agora** para {who}.{back}")
        else:
            how = "pela franquia" if tier == "subscription" else "com créditos"
            lines.append(f"**Recomendação: {NAMES[choice]}, {how}**, para {who}.")
    why = []
    for provider, reading in providers.items():
        name = NAMES[provider]
        if reading["state"] != "ok":
            why.append(f"a leitura do {name} está indisponível")
            continue
        unusable = account_block(reading, settings, decided_at)
        if unusable:
            why.append(f"a leitura do {name} não é confiável ({BLOCKS[unusable]})")
            continue
        for window in reading["windows"]:
            state = over(window, settings)
            if window["kind"] == "week":
                if state == "esgotada":
                    why.append(f"a franquia semanal do {name} acabou")
                elif state:
                    why.append(f"o {name} passou do limite semanal configurado ({settings['limits.week_block_pct']}%)")
                else:
                    why.append(f"o {name} tem {pct(100 - window['used_pct'])} da semana livres")
            elif state:
                why.append(f"a {window_name(window)} do {name} está {state}")
    if why:
        lines.append("Por quê: " + "; ".join(why) + ".")
    return lines


def describe_scope(labels, routes):
    route_labels = [l for l in labels if l.startswith("a rota ")]
    others = [l for l in labels if not l.startswith("a rota ")]
    parts = list(others[:1])
    if route_labels:
        parts.append(f"as {routes} rotas de subagente" if len(route_labels) == routes and routes > 1
                     else ", ".join(l[len("a rota "):] for l in route_labels))
    parts += others[1:]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " e " + parts[-1]


def changes(decisions, approved_only):
    """Grouped changes for approved (`would_change`) or proposed (`proposal_change`) targets only."""
    grouped, conversation, cron = {}, None, None
    for label, decision in consumers(decisions):
        change = decision.get("would_change") if approved_only else decision.get("proposal_change")
        if not change:
            continue
        text = f"{route(change['from'])} → {route(change['to'])}"
        if label == "a conversa":
            conversation = text
        elif label == "o cron":
            cron = text
        else:
            same = change["from"].get("effort") == change["to"].get("effort")
            key = (change["from"].get("model"), change["to"].get("model"), same)
            grouped.setdefault(key, []).append((label[len("a rota "):], change))
    lines = []
    if conversation:
        lines.append(f"• Conversa (modelo padrão do profile, vale em sessões novas): {conversation}")
    for (old, new, same), items in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        names = ", ".join(n for n, _ in items)
        if same:
            lines.append(f"• {old} → {new}, mesmo esforço: {names}")
        else:
            lines.extend(f"• {name}: {route(c['from'])} → {route(c['to'])}" for name, c in items)
    if cron:
        lines.append(f"• Cron: {cron}")
    return lines


def attention(status):
    lines = []
    for key, item in (status.get("settings_invalid") or {}).items():
        lines.append(f"• A configuração `{key}` tem um valor inválido; o plugin usa o padrão até você corrigir com `/quota-router config reset {key}`.")
    decisions = status.get("decisions") or {}
    cron = decisions.get("cron") or {}
    if cron.get("state") == "blocked_partial_pins":
        jobs = "; ".join(f"{p['job']} (falta {' e '.join(MISSING.get(m, m) for m in p['missing'])})"
                         for p in cron.get("partial_pins", []))
        lines.append(f"• Cron fica de fora: há jobs que fixam só parte da rota — {jobs}.")
    elif cron.get("state") == "jobs_unavailable":
        lines.append("• Cron fica de fora: o arquivo de jobs não pôde ser lido.")
    for label, decision in consumers(decisions) if "conversation" in decisions else []:
        if decision.get("state") == "disabled_by_setting" and label in ("a conversa", "o cron"):
            lines.append(f"• Recomendação para {label} desligada nas configurações.")
    if decisions.get("routes") and all(d.get("state") == "disabled_by_setting" for d in decisions["routes"].values()):
        lines.append("• Recomendação para os subagentes desligada nas configurações.")
    if decisions.get("state") == "inventory_unavailable":
        general = decisions.get("provider_level") or {}
        choice = general.get("choice")
        tip = (f" Recomendação geral: {NAMES[choice]}, {'pela franquia' if general.get('tier') == 'subscription' else 'com créditos'}."
               if choice else " Nenhum provedor pode ser usado agora.")
        lines.append("• A configuração do profile não pôde ser lida; não há recomendação por papel." + tip)
    if status.get("restart_required"):
        lines.append("• A configuração salva difere da que está carregada; reinicie o Hermes para aplicar.")
    if status.get("integrity") == "settings_or_mode_unavailable":
        lines.append("• O plugin não conseguiu ler a própria configuração; trate o resultado com cautela.")
    return lines


def status_text(status):
    stamp = when(status.get("decided_at")) if status.get("decided_at") else None
    mode = status.get("mode_effective")
    if mode != "observe":
        title = "desligado (OFF)" if mode == "off" else "indisponível"
        lines = [f"**Quota Router · {title}**", "Não lê cotas e não muda nada.",
                 "Para ver as recomendações: `/quota-router mode observe`."]
        extra = attention(status)
        return "\n".join(lines + (["", "**Atenção**", *extra] if extra else []))
    settings = status["settings"]
    providers = status["quota"]["providers"]
    decisions = status.get("decisions") or {}
    lines = [f"**Quota Router · Observe** — {stamp} · só recomenda, não muda nada", ""]
    if "conversation" in decisions:
        lines += recommendation(decisions, providers, settings, status.get("decided_at"))
    if status.get("decision_incomplete"):
        lines.append("**Decisão incompleta:** falta alguma leitura ou há configuração inválida; veja os detalhes abaixo antes de usar.")
    origin = QUOTA_SOURCES.get(status["quota"].get("source"), "fonte não identificada")
    lines += ["", f"**Cotas agora** (via {origin})"]
    lines += [provider_line(p, r, settings, status.get("decided_at")) for p, r in providers.items()]
    if "conversation" in decisions:
        approved_lines, proposed_lines = changes(decisions, True), changes(decisions, False)
        if approved_lines:
            lines += ["", "**O que mudaria** (mapa aprovado)"] + approved_lines
        if proposed_lines:
            note = "proposta para os papéis ainda sem mapa aprovado" if settings["roles"] else "proposta; o mapa de modelos ainda não foi aprovado"
            lines += ["", f"**O que mudaria** ({note})"] + proposed_lines
        notes = [MAP_NOTES[n] for n in decisions.get("map_notes") or [] if n in MAP_NOTES]
        if notes:
            lines += [""] + notes
    extra = attention(status)
    if extra:
        lines += ["", "**Atenção**"] + extra
    steps = []
    if "conversation" in decisions and decisions.get("map_status") == "proposal_not_approved" and not settings["roles"]:
        steps.append(f"• Aprovar o mapa proposto: `/quota-router config approve-map {decisions.get('variant', 'base')}`")
    steps += ["• Entender cada decisão: `/quota-router explain`", "• Ver e mudar preferências: `/quota-router config`"]
    lines += ["", "**Próximos passos**"] + steps
    lines += ["", "Fora do alcance: chamadas auxiliares, retries, fallbacks, chamadas em andamento e sessões gerenciadas abertas "
              "antes da decisão. Dados brutos: acrescente `--json` ao comando."]
    return "\n".join(lines)


def eligibility_line(provider, item, settings):
    name = NAMES[provider]
    if item.get("subscription"):
        score = item.get("score")
        if score is None:
            return f"• **{name}**: franquia disponível"
        pace = ("sobra mais cota do que tempo até a renovação" if score >= 1
                else "sobra um pouco menos cota do que tempo até a renovação")
        return f"• **{name}**: franquia disponível; folga {score:.2f}".replace(".", ",") + f" ({pace})"
    reason = block_text(item.get("blocked_by") or "", settings, item.get("blocked_window"))
    credit = CREDITS.get(item.get("credits_reason"), "")
    tail = f"; {credit}" if credit and item.get("credits_reason") != "model_not_eligible" else ""
    return f"• **{name}**: {reason}{tail}"


VARIANT_NAMES = {"base": "base", "fable": "com Fable", "astra": "com Astra", "fable+astra": "com Fable e Astra"}


def pair_text(pair):
    return " · ".join(f"{NAMES[p]} {route(pair[p])}" for p in ("openai-codex", "anthropic") if p in pair)


def variant_lines(proposal):
    variants = proposal.get("variants") or {}
    base = variants.get("base") or {}
    lines = [f"**Mapa base** (em uso: {VARIANT_NAMES.get(proposal.get('effective_variant') or '', '?')})"]
    lines += [f"• {role}: {pair_text(pair)}" for role, pair in base.items()]
    for name in ("fable", "astra", "fable+astra"):
        if name not in variants:
            continue
        swaps = {}
        for role, pair in variants[name].items():
            for provider, entry in pair.items():
                old = base.get(role, {}).get(provider) or {}
                if entry == old:
                    continue
                same = entry.get("effort") == old.get("effort")
                key = (provider, old.get("model"), entry.get("model"))
                swaps.setdefault(key, []).append(role if same else f"{role} ({route(entry)})")
        text = "; ".join(f"{NAMES[p]} troca {old} por {new} em {', '.join(roles)}"
                         for (p, old, new), roles in swaps.items())
        lines.append(f"• {VARIANT_NAMES[name]}: " + (text or "igual à base"))
    lines += [MAP_NOTES[n] for n in proposal.get("notes") or [] if n in MAP_NOTES]
    lines.append("Aprove uma variante com `/quota-router config approve-map <variante>`; até lá nada é aplicado.")
    return lines


def explain_text(status):
    decisions = status.get("decisions") or {}
    if status.get("mode_effective") != "observe" or "conversation" not in decisions:
        return status_text(status)
    settings = status["settings"]
    items = [(label, d) for label, d in consumers(decisions)
             if d.get("state") not in ("disabled_by_setting", "blocked_partial_pins", "jobs_unavailable")]
    lines = [f"**Quota Router · por que cada recomendação** — {when(status.get('decided_at'))}"]
    extra = attention(status)
    if status.get("decision_incomplete") or extra:
        lines += ["", "**Atenção**"]
        if status.get("decision_incomplete"):
            lines.append("• Decisão incompleta: falta alguma leitura ou há configuração inválida; a explicação usa os padrões.")
        lines += extra
    situations = {}
    for label, decision in items:
        key = tuple(eligibility_line(p, e, settings) for p, e in (decision.get("eligibility") or {}).items())
        situations.setdefault(key, []).append((label, decision))
    routes = len(decisions.get("routes", {}))
    for situation, members in situations.items():
        if len(situations) > 1:
            lines += ["", f"**Para {describe_scope([l for l, _ in members], routes)}**"]
        else:
            lines += ["", "**Situação dos provedores**"]
        lines += list(situation)
        outcomes = {}
        for label, decision in members:
            outcomes.setdefault((decision.get("choice"), decision.get("tier"), decision.get("reason")), []).append(label)
        only = sum(1 for _, d in members[:1] for e in (d.get("eligibility") or {}).values() if e.get("subscription")) == 1
        for (choice, tier, reason), labels in outcomes.items():
            who = describe_scope(labels, routes)
            if only and tier == "subscription" and reason in ("best_pacing", "previous_preference_kept", "principal_eligible"):
                reason = "only_subscription"
            how = "pela franquia" if tier == "subscription" else "com créditos"
            head = f"**Decisão**: {NAMES[choice]}, {how}, para {who}" if choice else f"**Decisão**: nenhum provedor para {who}"
            lines.append(f"{head} — {reason_text(reason, settings)}.")
    for approved_only, title in ((True, "Mudanças por papel (mapa aprovado)"), (False, "Mudanças por papel (proposta, ainda não aplicada)")):
        rows = []
        for label, decision in consumers(decisions):
            change = decision.get("would_change") if approved_only else decision.get("proposal_change")
            if change:
                name = label.replace("a rota ", "").replace("a conversa", "Conversa (padrão do profile, sessões novas)").replace("o cron", "Cron")
                rows.append(f"• {name}: {route(change['from'])} → {route(change['to'])}")
        if rows:
            lines += ["", f"**{title}**"] + rows
    lines += ["", f"Folga = parte livre da cota semanal ÷ parte da semana que falta até a renovação. "
              f"Para trocar de provedor, o outro precisa ter mais de {settings['limits.hysteresis_pct']}% de vantagem."]
    if (status.get("map") or {}).get("variants"):
        lines += [""] + variant_lines(status["map"])
    return "\n".join(lines)


def value_text(key, value):
    if isinstance(value, bool):
        return "ligado" if value else "desligado"
    if key == "roles":
        return f"aprovado para {len(value)} papéis" if value else "não aprovado"
    return str(value)


def config_text(payload):
    settings, invalid = payload["settings"], payload.get("settings_invalid") or {}
    lines = ["**Configurações do Quota Router**"]
    if payload.get("changed"):
        key = next(iter(payload["changed"]))
        lines.append(f"Gravado: `{key}` = {value_text(key, settings[key])}.")
    lines += ["Mude com `/quota-router config set <chave> <valor>`; volte ao padrão com `/quota-router config reset <chave>`.", ""]
    section = None
    for key in SETTINGS_TEXT:
        group, text = SETTINGS_TEXT[key]
        if group != section:
            lines += (["", f"**{group}**"] if section else [f"**{group}**"])
            section = group
        current = value_text(key, settings[key])
        default = "" if settings[key] == DEFAULTS[key] else f" (padrão: {value_text(key, DEFAULTS[key])})"
        flag = " — valor salvo inválido; usando o padrão" if key in invalid else ""
        lines.append(f"• `{key}` = {current}{default}{flag}: {text}")
    lines += ["", "Mapa de modelos: aprove com `/quota-router config approve-map base` (ou `fable`, `astra`, `fable+astra`)."]
    return "\n".join(lines)


def render(command, payload):
    """Chat text for one command result."""
    if payload.get("error"):
        head = f"**Não foi possível:** {error_text(payload['error'])}"
        body = status_text(payload) if "mode_effective" in payload else ""
        return head + ("\n\n" + body if body else "")
    if command == "config":
        return config_text(payload)
    if command == "explain":
        return explain_text(payload)
    if command == "mode":
        return f"Modo alterado para **{'Observe' if payload.get('mode_effective') == 'observe' else 'OFF'}**.\n\n" + status_text(payload)
    return status_text(payload)
