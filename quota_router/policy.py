"""Deterministic next-task decision (spec section 5; HQR-20 amendment sections 6, 13 and 14).

No inference, no network: inputs are normalized readings and effective settings.
Thresholds, pacing scores and hysteresis use exact fractions of the reported percentages and times.
"""
from datetime import datetime
from fractions import Fraction

from .settings import PROVIDERS


def _fraction(value):
    return Fraction(str(value))


def eligibility(reading, settings, now, model=None, blocked=None):
    """Subscription eligibility, pacing score and credit eligibility of one provider."""
    provider = reading["provider"]
    result = {"subscription": False, "score": None, "blocked_by": None, "resets": [], "credits": False, "credits_reason": None,
              "_score": None}
    if blocked:
        result["blocked_by"] = blocked
        result["credits_reason"] = "model_not_eligible"
        return result
    if reading["state"] != "ok":
        result["blocked_by"] = "unknown:" + str(reading["reason"])
        result["credits_reason"] = "reading_unknown"
        return result
    session_block = Fraction(settings["limits.session_block_pct"], 100)
    week_block = Fraction(settings["limits.week_block_pct"], 100)
    family_model = (model or "").lower()
    scores, exhausted, inconsistent = [], False, False
    for window in reading["windows"]:
        if window["kind"] == "model_week" and not (window["family"] and window["family"] in family_model):
            continue
        result["resets"].append(window["reset_at"])
        delta = datetime.fromisoformat(window["reset_at"]) - now
        remaining = Fraction(delta.days * 86400 + delta.seconds, 1) + Fraction(delta.microseconds, 1000000)
        remaining /= window["duration_s"]
        if not 0 < remaining <= 1:
            inconsistent = True
            continue
        used = _fraction(window["used_pct"]) / 100
        if used >= (session_block if window["kind"] == "session" else week_block):
            exhausted = True
            if not result["blocked_by"]:
                result["blocked_by"] = "session" if window["kind"] == "session" else "week"
                result["blocked_window"] = {"kind": window["kind"], "family": window.get("family")}
            continue
        if window["kind"] != "session":
            scores.append((1 - used) / remaining)
    if inconsistent:
        result["blocked_by"] = "inconsistent_window"
        result["credits_reason"] = "reading_inconsistent"
        return result
    upstream = reading.get("upstream") or {}
    if not exhausted and scores and (upstream.get("allowed") is False or upstream.get("limit_reached") is True):
        # Free windows with an explicit upstream denial contradict each other: neither tier is safe.
        result["blocked_by"] = "upstream_denied_contradiction"
        result["credits_reason"] = "reading_inconsistent"
        return result
    if not exhausted and scores:
        result["subscription"] = True
        result["_score"] = min(scores)
        result["score"] = float(result["_score"])
        return result
    if not exhausted:
        result["blocked_by"] = "no_week_window"
        result["credits_reason"] = "reading_inconsistent"
        return result
    result["credits"], result["credits_reason"] = _credits(provider, reading, settings)
    return result


def _credits(provider, reading, settings):
    if not settings.get("credits." + provider, False):
        return False, "credits_disabled"
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


def decide(role, readings, settings, now, previous=None, models=None, blocked=None):
    """Choose the provider for the next task of a role; None when nothing is eligible.

    `blocked` maps a provider to the reason its target model is not eligible (Fable or Astra not qualified).
    """
    models, blocked = models or {}, blocked or {}
    principal = settings["principal"]
    elig = {p: eligibility(readings[p], settings, now, models.get(p), blocked.get(p)) for p in PROVIDERS if p in readings}
    exact = {p: e.pop("_score") for p, e in elig.items()}
    scores = {p: e["score"] for p, e in elig.items()}
    subs = [p for p in PROVIDERS if p in elig and elig[p]["subscription"]]
    base = {"role": role, "scores": scores, "eligibility": elig, "resets": [], "previous": previous}
    if subs:
        if role == "conversation" and settings["conversation.policy"] == "principal_first" and principal in subs:
            return dict(base, choice=principal, tier="subscription", reason="principal_eligible")
        if previous in subs:
            threshold = exact[previous] * (1 + Fraction(settings["limits.hysteresis_pct"], 100))
            challengers = [p for p in subs if p != previous and exact[p] > threshold]
            if challengers:
                best = max(challengers, key=lambda p: (exact[p], p == principal))
                return dict(base, choice=best, tier="subscription", reason="challenger_above_hysteresis")
            return dict(base, choice=previous, tier="subscription", reason="previous_preference_kept")
        top = max(exact[p] for p in subs)
        tied = [p for p in subs if exact[p] == top]
        choice = principal if principal in tied else tied[0]
        return dict(base, choice=choice, tier="subscription", reason="best_pacing")
    paid = [p for p in PROVIDERS if p in elig and elig[p]["credits"]]
    if paid:
        choice = principal if principal in paid else paid[0]
        return dict(base, choice=choice, tier="credits", reason="credits_after_subscriptions")
    resets = sorted({r for e in elig.values() for r in e["resets"]})
    return dict(base, choice=None, tier=None, reason="no_eligible_candidate", resets=resets)
