# Implements decisions/product-spec.md, section 5; decisions/hqr-20-amendment.md, sections 6/13/14 and D10;
# decisions/hqr-38-spec.md, D-28 to D-31 (states Livre/Pressionado/Esgotado/Desconhecido and safety net).
"""Deterministic next-task decision (spec section 5; HQR-20 amendment sections 6, 13 and 14).

No inference, no network: inputs are normalized readings and effective settings.
Thresholds, pacing scores and hysteresis use exact fractions of the reported percentages and times.
"""
from datetime import datetime
from fractions import Fraction

from .settings import PROVIDERS


def _fraction(value):
    return Fraction(str(value))


# decisions/hqr-38-spec.md, A23: a not-started window may report a reset slightly beyond now + duration.
CLOCK_TOLERANCE_S = 120


def _applies(window, model):
    """Account windows always apply; a model window applies only to the model or family it names (D-31)."""
    kind = window["kind"]
    if kind in ("session", "week"):
        return True
    if kind in ("model_week", "model_unqualified") and window.get("family"):
        return window["family"] in model
    return bool(window.get("model")) and window["model"] == model


def _remaining(window, now):
    """Fraction of the window still ahead; None for an idle window without reset (A22)."""
    if window["reset_at"] is None:
        return None
    delta = datetime.fromisoformat(window["reset_at"]) - now
    seconds = Fraction(delta.days * 86400 + delta.seconds, 1) + Fraction(delta.microseconds, 1000000)
    remaining = seconds / window["duration_s"]
    # decisions/hqr-38-spec.md, A23: bounded clock tolerance; anything further stays inconsistent.
    if 1 < remaining <= 1 + Fraction(CLOCK_TOLERANCE_S, window["duration_s"]):
        return Fraction(1)
    return remaining


def eligibility(reading, settings, now, model=None, blocked=None):
    """Quota state (decisions/hqr-38-spec.md, D-31), pacing score and credit eligibility of one provider.

    `subscription` is true only for Livre; `pressured` marks Pressionado, a candidate only when no provider is Livre.
    """
    provider = reading["provider"]
    result = {"state": "unknown", "subscription": False, "pressured": False, "score": None, "blocked_by": None, "resets": [],
              "credits": False, "credits_reason": None, "_score": None}
    if blocked:
        result["blocked_by"] = blocked
        result["credits_reason"] = "model_not_eligible"
        return result
    if reading["state"] != "ok":
        result["blocked_by"] = "unknown:" + str(reading["reason"])
        result["credits_reason"] = "reading_unknown"
        return result
    pressure = Fraction(settings["limits.session_block_pct"], 100)
    week_block = Fraction(settings["limits.week_block_pct"], 100)
    target = (model or "").lower()
    windows = [w for w in reading["windows"] + reading.get("model_windows", []) if _applies(w, target)]
    scores, exhausted_by, pressured_by, unknown_by = [], None, None, None
    for window in windows:
        if window["kind"] == "model_unqualified":
            unknown_by = "model_window_unqualified"
            result["requalification_required"] = True
            continue
        if window["reset_at"] is not None:
            result["resets"].append(window["reset_at"])
        remaining = _remaining(window, now)
        if remaining is not None and not 0 < remaining <= 1:
            reason = "reset_passed" if remaining <= 0 else "inconsistent_window"
            if unknown_by != "model_window_unqualified":
                unknown_by = reason if reason == "reset_passed" else unknown_by or reason
            continue
        used = _fraction(window["used_pct"]) / 100
        if window["kind"] in ("session", "model_session"):
            # decisions/hqr-38-spec.md, D-31: 5 h at the configured threshold presses; only 100% exhausts.
            if used >= 1:
                exhausted_by = exhausted_by or ("session", window)
            elif used >= pressure:
                pressured_by = pressured_by or ("session", window)
            continue
        # decisions/product-spec.md, section 5: reaching the configured week threshold exhausts, with no rounding slack.
        if used >= week_block:
            exhausted_by = exhausted_by or ("week", window)
            continue
        if remaining is not None:
            scores.append((1 - used) / remaining)
        elif used == 0:
            # decisions/hqr-38-spec.md, A22: a week that has not started has its full duration ahead.
            scores.append(Fraction(1))
    if unknown_by:
        # A23 covers only temporal inconsistency in qualified windows, never format drift or an elapsed reset (SOL-03).
        result["blocked_by"] = unknown_by
        if unknown_by == "inconsistent_window":
            result["credits"], result["credits_reason"] = _credits(provider, reading, settings)
        else:
            result["credits_reason"] = "reading_inconsistent"
        return result
    if exhausted_by:
        result["state"] = "exhausted"
        result["blocked_by"] = exhausted_by[0]
        result["blocked_window"] = {"kind": exhausted_by[1]["kind"], "family": exhausted_by[1].get("family")}
        result["credits"], result["credits_reason"] = _credits(provider, reading, settings)
        return result
    if reading.get("credits_only") and not scores:
        # decisions/hqr-38-spec.md, A27: a credits-only plan is exhausted with credits, subject to credits.<provider>.
        result["state"] = "exhausted"
        result["blocked_by"] = "credits_only_plan"
        result["credits"], result["credits_reason"] = _credits(provider, reading, settings)
        return result
    upstream = reading.get("upstream") or {}
    if scores and (upstream.get("allowed") is False or upstream.get("limit_reached") is True):
        # Free windows with an explicit upstream denial contradict each other: neither tier is safe.
        result["blocked_by"] = "upstream_denied_contradiction"
        result["credits_reason"] = "reading_inconsistent"
        return result
    if not scores:
        result["blocked_by"] = "no_week_window"
        result["credits_reason"] = "reading_inconsistent"
        return result
    result["_score"] = min(scores)
    result["score"] = float(result["_score"])
    if pressured_by:
        result.update(state="pressured", pressured=True, blocked_by=pressured_by[0])
        result["blocked_window"] = {"kind": pressured_by[1]["kind"], "family": pressured_by[1].get("family")}
        return result
    result.update(state="free", subscription=True)
    return result


# decisions/hqr-20-amendment.md, section 14: credits require explicit permission plus verified positive balance and limits.
def _credits(provider, reading, settings):
    if not settings.get("credits." + provider, False):
        return False, "credits_disabled"
    # D-43: a carried balance cannot authorize a paid route or fallback.
    if reading.get("last_known"):
        return False, "credits_not_verifiable"
    credits = reading.get("credits") or {}
    if not credits.get("visible"):
        return False, "credits_not_verifiable"
    limits = (credits.get("overage_limit_reached"), credits.get("spend_reached"))
    if True in limits:
        return False, "credits_limit_reached"
    if limits != (False, False):
        return False, "credits_limits_not_verifiable"
    # Fail closed: a positive finite balance is required even when the account reports unlimited credits.
    if credits.get("has_credits") is True and credits.get("balance_positive") is True:
        return True, "credits_available"
    return False, "credits_empty"


def _rank(group, exact, previous, principal, hysteresis, prefix=""):
    """Pacing order inside one group; hysteresis protects only a previous choice of the same group (D-31)."""
    # decisions/hqr-20-amendment.md, section 6/D10: a challenger must strictly exceed the configured hysteresis margin.
    if previous in group:
        threshold = exact[previous] * (1 + Fraction(hysteresis, 100))
        challengers = [p for p in group if p != previous and exact[p] > threshold]
        if challengers:
            return max(challengers, key=lambda p: (exact[p], p == principal)), prefix + "challenger_above_hysteresis"
        return previous, prefix + "previous_preference_kept"
    top = max(exact[p] for p in group)
    tied = [p for p in group if exact[p] == top]
    return (principal if principal in tied else tied[0]), prefix + "best_pacing"


def decide(role, readings, settings, now, previous=None, models=None, blocked=None):
    """Choose the provider for the next task of a role; None when nothing is eligible.

    Order (decisions/hqr-38-spec.md, D-31): Livre; then Pressionado; then allowed credits; otherwise nothing changes.
    `blocked` maps a provider to the reason its target model is not eligible (Fable or Astra not qualified).
    """
    models, blocked = models or {}, blocked or {}
    principal = settings["principal"]
    elig = {p: eligibility(readings[p], settings, now, models.get(p), blocked.get(p)) for p in PROVIDERS if p in readings}
    exact = {p: e.pop("_score") for p, e in elig.items()}
    scores = {p: e["score"] for p, e in elig.items()}
    states = {p: e["state"] for p, e in elig.items()}
    base = {"role": role, "scores": scores, "states": states, "eligibility": elig, "resets": [], "previous": previous}
    hysteresis = settings["limits.hysteresis_pct"]
    free = [p for p in PROVIDERS if states.get(p) == "free"]
    if free:
        if role == "conversation" and settings["conversation.policy"] == "principal_first" and principal in free:
            return dict(base, choice=principal, tier="subscription", reason="principal_eligible")
        choice, reason = _rank(free, exact, previous, principal, hysteresis)
        return dict(base, choice=choice, tier="subscription", reason=reason)
    pressured = [p for p in PROVIDERS if states.get(p) == "pressured"]
    if pressured:
        # decisions/hqr-38-spec.md, D-31: with every 5 h window pressed, weekly slack decides for every role.
        choice, reason = _rank(pressured, exact, previous, principal, hysteresis, "pressured_")
        return dict(base, choice=choice, tier="subscription", reason=reason)
    # decisions/hqr-20-amendment.md, section 14: every eligible subscription outranks all paid-credit candidates.
    paid = [p for p in PROVIDERS if p in elig and elig[p]["credits"]]
    if paid:
        choice = principal if principal in paid else paid[0]
        return dict(base, choice=choice, tier="credits", reason="credits_after_subscriptions")
    resets = sorted({r for e in elig.values() for r in e["resets"]})
    return dict(base, choice=None, tier=None, reason="no_eligible_candidate", resets=resets)


# D-28/D-29, SOL-01: share every usable candidate; only the native consumer knows its effective pinned backend.
def fallback_chain(decision, pair):
    """`fallback_providers` entries for a decided role; None when nothing was chosen.

    Native entries (hermes_cli/fallback_config.py) carry `provider` and `model`; the native resolver supplies endpoint,
    API mode and credentials, and effort follows the native reasoning resolution, so no other field is written.
    """
    choice = decision.get("choice")
    if choice is None or not pair:
        return None
    rank = {"free": 0, "pressured": 1}
    usable, excluded = [], {}
    for provider in PROVIDERS:
        if provider not in pair:
            continue
        verdict = (decision.get("eligibility") or {}).get(provider)
        state = verdict["state"] if verdict else "unknown"
        if state in rank or (verdict and verdict["credits"]):
            usable.append((rank.get(state, 2), provider))
        elif verdict and str(verdict.get("blocked_by") or "").startswith("model_not_eligible"):
            excluded[provider] = "model_not_eligible"
        else:
            excluded[provider] = "exhausted_without_credits" if state == "exhausted" else "unknown"
    chain = [{"provider": p, "model": pair[p]["model"]}
             for _, p in sorted(usable, key=lambda item: (item[0], item[1] != choice, item[1]))]
    return {"chain": chain, "excluded": excluded}
