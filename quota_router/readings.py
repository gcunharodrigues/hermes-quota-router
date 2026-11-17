# Implements decisions/hqr-20-amendment.md, sections 13/14 and AC-16; README.md, HQR-23/HQR-25/HQR-35;
# decisions/hqr-38-spec.md, "Correções de leitura e tipos de plano" (A22, A23, A26, A27, A29, A31, A32, A34, A38).
"""Native quota readings (HQR-20 amendment, section 14; AC-16).

Uses only the host reader `agent.account_usage.fetch_account_usage(provider, read_only=True)`.
The plugin never sees tokens; from the Codex `raw` body it keeps only an allowlist of credit and availability fields.
Any contract drift (unknown window label, duplicate window, provider mismatch, malformed shape) becomes an unknown reading.
"""
from datetime import datetime, timedelta, timezone
import inspect
import math
import re

SESSION_S = 18000
WEEK_S = 604800
# README.md, HQR-35/HQR-25: the usage API answered Retry-After: 300; status must not amplify that rate limit.
FAILURE_BACKOFF_S = 300
MIN_BACKOFF_S = 30
MAX_BACKOFF_S = 3600
# decisions/hqr-38-spec.md, A29: a structural verdict on a received reading retries on the next cycle, not after 300 s.
STRUCTURAL = ("reset_passed", "stale_reading", "future_reading")
# decisions/hqr-38-spec.md, A26: a published window of 28 days or more is a monthly allowance, which is not supported.
MONTHLY_MIN_S = 28 * 86400
# decisions/hqr-38-spec.md, A31: per-model Codex windows are qualified only for the two published durations.
MODEL_KINDS = {SESSION_S: "model_session", WEEK_S: "model_week"}
CODEX_WINDOW_KEYS = ("primary_window", "secondary_window")
MODEL_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

# Native window labels (agent/account_usage.py) -> (kind, duration in seconds, model family); native scope must agree.
LABELS = {
    "Session": ("session", SESSION_S, None),
    "Current session": ("session", SESSION_S, None),
    "Weekly": ("week", WEEK_S, None),
    "Current week": ("week", WEEK_S, None),
    "Opus week": ("model_week", WEEK_S, "opus"),
    "Sonnet week": ("model_week", WEEK_S, "sonnet"),
}
SCOPES = {"session": "account", "week": "account", "model_week": "model"}
SOURCE = re.compile(r"^[a-z0-9_]{1,40}$")


# README.md, HQR-35: discard private fields at the callback boundary, before retaining any native diagnostic.
class _NativeFailure:
    def __init__(self, details):
        self.details = {}
        if not isinstance(details, dict):
            return
        kind = details.get("kind")
        if isinstance(kind, str) and kind in ("http", "timeout", "network", "error"):
            self.details["kind"] = kind
        status = details.get("status")
        if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
            self.details["status"] = status
        seconds = details.get("retry_after_s")
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
            if isinstance(seconds, int) or math.isfinite(seconds):
                self.details["retry_after_s"] = seconds


def native_importer():
    """Return the native reader, or None when this process has no Hermes host."""
    try:
        from agent.account_usage import fetch_account_usage
    except Exception:
        return None
    # README.md, HQR-35: inspect only; probing a reader could issue a real query or require credentials.
    try:
        parameter = inspect.signature(fetch_account_usage).parameters.get("on_error")
    except (TypeError, ValueError):
        parameter = None
    if parameter is None or parameter.kind not in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
        return lambda provider: fetch_account_usage(provider, read_only=True)

    def read(provider):
        failure = None

        def on_error(details):
            nonlocal failure
            if failure is None:
                failure = _NativeFailure(details)

        options: dict = {"read_only": True, "on_error": on_error}
        snapshot = fetch_account_usage(provider, **options)
        return snapshot if snapshot is not None else failure

    return read


def _unknown(provider, reason, fetched_at=None):
    return {"provider": provider, "state": "unknown", "reason": reason, "source": None, "fetched_at": fetched_at,
            "age_s": None, "windows": [], "credits": {"visible": False}, "astra_available": None}


def _aware(value):
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _flag(source, key):
    value = source.get(key) if isinstance(source, dict) else None
    return value if isinstance(value, bool) else None


def _positive_balance(value):
    """True only for a finite positive number or numeric string; None for anything else."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number > 0 if math.isfinite(number) else None


# decisions/hqr-20-amendment.md, section 14: retain only the explicit credit allowlist, never the raw account response.
def _codex_credits(raw):
    credits = raw.get("credits")
    if not isinstance(credits, dict):
        return {"visible": False}
    return {"visible": True, "has_credits": _flag(credits, "has_credits"), "unlimited": _flag(credits, "unlimited"),
            "balance_positive": _positive_balance(credits.get("balance")),
            "overage_limit_reached": _flag(credits, "overage_limit_reached"),
            "spend_reached": _flag(raw.get("spend_control"), "reached")}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _codex_slots(raw):
    """Codex rate-limit window slots that carry numeric usage, in response order."""
    rate_limit = raw.get("rate_limit")
    found = []
    for key in CODEX_WINDOW_KEYS:
        window = rate_limit.get(key) if isinstance(rate_limit, dict) else None
        # decisions/hqr-38-spec.md, A38: the native reader skips a window whose usage is null, so its duration is not evidence.
        # A slot that does not carry the usage field at all keeps the S2 duration-only contract.
        if isinstance(window, dict) and window and ("used_percent" not in window or _number(window["used_percent"])):
            found.append(window)
    return found


def _codex_durations(raw):
    """Durations the Codex response publishes (`limit_window_seconds`), one per window slot with usage, in response order.

    The host emits one window per slot that carries usage, in the same order; any slot it skipped makes the lists differ in length.
    """
    found = []
    for window in _codex_slots(raw):
        seconds = window.get("limit_window_seconds") if isinstance(window, dict) else None
        found.append(seconds if isinstance(seconds, int) and not isinstance(seconds, bool) else None)
    return found


# decisions/hqr-38-spec.md, A26: a monthly allowance (ChatGPT Go) is reported with an explicit unsupported reason.
def _monthly(raw):
    plan = raw.get("plan_type")
    if isinstance(plan, str) and plan.strip().lower() == "go":
        return True
    return any(_number(w.get("limit_window_seconds")) and w["limit_window_seconds"] >= MONTHLY_MIN_S for w in _codex_slots(raw))


# decisions/hqr-38-spec.md, A34: an unpublished window slot (the announced token allowance) needs requalification.
def _new_format(raw):
    rate_limit = raw.get("rate_limit")
    if not isinstance(rate_limit, dict):
        return False
    return any(isinstance(key, str) and key.endswith("_window") and key not in CODEX_WINDOW_KEYS for key in rate_limit)


def _when(value):
    """The native `_parse_dt` shapes: epoch seconds or ISO text; None when absent or unparseable."""
    if _number(value) and math.isfinite(value):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value.strip():
        text = value.strip()
        text = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return None
        return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return None


# decisions/hqr-38-spec.md, A31: `additional_rate_limits` cap only the model they name; anything unqualified fails closed for it.
def _model_windows(raw, now):
    windows = []
    extras = raw.get("additional_rate_limits")
    for extra in extras if isinstance(extras, list) else []:
        name = extra.get("limit_name") if isinstance(extra, dict) else None
        model = re.sub(r"\s+", "-", name.strip().lower()) if isinstance(name, str) else ""
        rate_limit = extra.get("rate_limit") if isinstance(extra, dict) else None
        if not MODEL_ID.match(model):
            continue
        unqualified = {"kind": "model_unqualified", "family": None, "model": model, "used_pct": None, "used": None,
                       "reset_at": None, "duration_s": None}
        if not isinstance(rate_limit, dict) or _new_format({"rate_limit": rate_limit}):
            windows.append(unqualified)
            continue
        for key in CODEX_WINDOW_KEYS:
            window = rate_limit.get(key)
            if window is None:
                continue
            if not isinstance(window, dict):
                windows.append(unqualified)
                continue
            if window.get("used_percent") is None:
                continue
            used, seconds, reset = window.get("used_percent"), window.get("limit_window_seconds"), _when(window.get("reset_at"))
            kind = MODEL_KINDS.get(seconds) if _number(seconds) else None
            # An unparseable reset is not an idle window: only an absent reset may be (A22).
            readable = reset is not None or window.get("reset_at") in (None, "")
            valid = (_number(used) and math.isfinite(used) and used >= 0 and kind and readable
                     and (reset > now if reset is not None else used == 0))
            if not valid:
                windows.append({"kind": "model_unqualified", "family": None, "model": model, "used_pct": None, "used": None,
                                "reset_at": None, "duration_s": None})
                continue
            used = min(used, 100)
            windows.append({"kind": kind, "family": None, "model": model, "used_pct": used, "used": used / 100,
                            "reset_at": reset.astimezone(timezone.utc).isoformat() if reset else None, "duration_s": seconds})
    return windows


def _upstream(raw):
    rate_limit = raw.get("rate_limit")
    return {"allowed": _flag(rate_limit, "allowed"), "limit_reached": _flag(rate_limit, "limit_reached")}


def _astra(raw):
    usage = raw.get("model_usage")
    return _flag(usage.get("gpt-6-astra") if isinstance(usage, dict) else None, "available")


def _normalize(provider, snapshot, now, max_age_s):
    if not all(hasattr(snapshot, name) for name in ("provider", "fetched_at", "windows")):
        return _unknown(provider, "malformed_snapshot")
    if snapshot.provider != provider:
        return _unknown(provider, "provider_mismatch")
    if getattr(snapshot, "unavailable_reason", None):
        return _unknown(provider, "provider_unavailable")
    fetched = getattr(snapshot, "fetched_at", None)
    if not _aware(fetched):
        return _unknown(provider, "invalid_timestamp")
    age = (now - fetched).total_seconds()
    stamp = fetched.astimezone(timezone.utc).isoformat()
    if age < 0:
        return _unknown(provider, "future_reading", stamp)
    if age > max_age_s:
        return _unknown(provider, "stale_reading", stamp)
    windows, seen = [], set()
    for window in tuple(getattr(snapshot, "windows", None)):
        label = getattr(window, "label", None)
        if not isinstance(label, str) or label not in LABELS:
            return dict(_unknown(provider, "unknown_window_label", stamp), requalification_required=True)
        kind, duration, family = LABELS[label]
        if getattr(window, "scope", None) != SCOPES[kind]:
            return _unknown(provider, "scope_mismatch", stamp)
        if (kind, family) in seen:
            return _unknown(provider, "conflicting_windows", stamp)
        seen.add((kind, family))
        used, reset = getattr(window, "used_percent", None), getattr(window, "reset_at", None)
        if not _number(used) or not used >= 0 or used != used or math.isinf(used):
            return _unknown(provider, "malformed_window", stamp)
        # decisions/hqr-38-spec.md, A32: providers may report more than 100%; it is a full window, not a malformed one.
        used = min(used, 100)
        if reset is None and used > 0 and kind == "model_week":
            # SOL-06: a missing model reset invalidates that family, not the account or unrelated models.
            windows.append({"kind": "model_unqualified", "family": family, "model": None, "used_pct": None, "used": None,
                            "reset_at": None, "duration_s": None})
            continue
        if reset is None and used == 0:
            # decisions/hqr-38-spec.md, A22: only proved idle usage qualifies for an absent reset.
            windows.append({"kind": kind, "family": family, "used_pct": used, "used": used / 100, "reset_at": None,
                            "duration_s": duration})
            continue
        if not _aware(reset):
            return _unknown(provider, "malformed_window", stamp)
        if reset <= now:
            return _unknown(provider, "reset_passed", stamp)
        windows.append({"kind": kind, "family": family, "used_pct": used, "used": used / 100,
                        "reset_at": reset.astimezone(timezone.utc).isoformat(), "duration_s": duration})
    raw = getattr(snapshot, "raw", None)
    raw = raw if isinstance(raw, dict) else {}
    credits_only = False
    if provider == "openai-codex":
        if _monthly(raw):
            return _unknown(provider, "monthly_plan_unsupported", stamp)
        if _new_format(raw):
            return dict(_unknown(provider, "format_requalification_required", stamp), requalification_required=True)
        # decisions/hqr-38-spec.md, A27: no window at all plus visible credits is a credits-only plan (exhausted with credits).
        credits_only = not windows and not _codex_slots(raw) and isinstance(raw.get("credits"), dict)
    if not credits_only and not any(w["kind"] == "week" for w in windows):
        return _unknown(provider, "no_week_window", stamp)
    if provider == "openai-codex":
        # decisions/hqr-20-amendment.md, section 14/AC-16: positional labels are not evidence of the published window duration.
        published = _codex_durations(raw)
        if published != [w["duration_s"] for w in windows]:
            return dict(_unknown(provider, "window_duration_unqualified", stamp), requalification_required=True)
    source = getattr(snapshot, "source", None)
    extra = {"credits_only": True} if credits_only else {}
    if provider == "openai-codex":
        extra["model_windows"] = _model_windows(raw, now)
    return {**extra, "provider": provider, "state": "ok", "reason": None, "source": source if isinstance(source, str) and SOURCE.match(source) else None,
            "fetched_at": stamp, "age_s": age, "windows": windows,
            "credits": _codex_credits(raw) if provider == "openai-codex" else {"visible": False},
            "astra_available": _astra(raw) if provider == "openai-codex" else None,
            "upstream": _upstream(raw) if provider == "openai-codex" else {"allowed": None, "limit_reached": None}}


def normalize(provider, snapshot, now, max_age_s):
    """One reading with windows as fractions, or an unknown state with a reason; never free capacity."""
    if snapshot is None:
        return _unknown(provider, "no_snapshot")
    # README.md, HQR-35: only a native failure callback establishes a transport reason, never absence alone.
    if isinstance(snapshot, _NativeFailure):
        details = snapshot.details
        kind, status = details.get("kind", ""), details.get("status")
        reason = {"timeout": "timeout", "network": "network_error", "error": "reader_error"}.get(kind, "no_snapshot")
        if kind == "http" and status is not None:
            reason = f"http_{status}"
        reading = _unknown(provider, reason)
        if "retry_after_s" in details:
            reading["retry_after_s"] = details["retry_after_s"]
        return reading
    try:
        return _normalize(provider, snapshot, now, max_age_s)
    except Exception:
        return _unknown(provider, "malformed_snapshot")


# decisions/hqr-20-amendment.md, AC-16: all readings must still be fresh and pre-reset at the same final decision time.
def revalidate(readings, now, max_age_s):
    """Readings judged again at one decision time: an expired or reset-crossed reading becomes unknown."""
    result = {}
    for provider, reading in readings.items():
        if reading["state"] != "ok":
            result[provider] = reading
            continue
        # SOL-03: model-only reset expiry forces cache refresh, but at decision time it blocks only that model.
        # eligibility rechecks each applicable reset at `now`, without the A23 credit exception for elapsed windows.
        valid = _still_valid(reading, now, max_age_s, model_resets=False)
        if valid is not None:
            result[provider] = valid
            continue
        age = (now - datetime.fromisoformat(reading["fetched_at"])).total_seconds()
        reason = "future_reading" if age < 0 else "stale_reading" if age > max_age_s else "reset_passed"
        result[provider] = _unknown(provider, reason, reading["fetched_at"])
    return result


def _still_valid(reading, now, max_age_s, model_resets=True):
    if reading["state"] != "ok":
        return None
    age = (now - datetime.fromisoformat(reading["fetched_at"])).total_seconds()
    if not 0 <= age <= max_age_s:
        return None
    # A22: an idle window without a reset never crosses one; SOL-03: cached model windows also expire.
    windows = reading["windows"] + (reading.get("model_windows", []) if model_resets else [])
    if any(w["reset_at"] is not None and datetime.fromisoformat(w["reset_at"]) <= now
           for w in windows if model_resets or w["kind"] in ("session", "week")):
        return None
    return dict(reading, age_s=age)


# README.md, HQR-35: unknown fetch results have their own retry deadline, independent of success freshness.
def _backing_off(reading, now):
    if reading["state"] != "unknown" or not reading.get("retry_at"):
        return None
    retry_at = datetime.fromisoformat(reading["retry_at"])
    return dict(reading) if now < retry_at else None


def collect(providers, now, max_age_s, reader=None, cache=None, importer=None, clock=None):
    """Reuse fresh quota or a backed-off failure; returns (readings, queries issued).

    `now` validates cache hits; a failure's backoff starts at `clock()` sampled after its fetch.
    """
    if reader is None:
        reader = (importer or native_importer)()
    readings, queries = {}, 0
    for provider in providers:
        cached = (cache or {}).get(provider)
        reused = (_still_valid(cached, now, max_age_s) or _backing_off(cached, now)) if cached else None
        if reused is not None:
            readings[provider] = reused
            continue
        if reader is None:
            readings[provider] = _unknown(provider, "reader_unavailable")
            continue
        queries += 1
        try:
            snapshot = reader(provider)
        except Exception:
            snapshot = _NativeFailure({"kind": "error"})
        completed_at = clock() if clock else now
        reading = normalize(provider, snapshot, completed_at, max_age_s)
        if reading["state"] == "unknown":
            # README.md, HQR-35: never reuse a prior successful quota as capacity after a failed refresh.
            failed_at = completed_at.astimezone(timezone.utc)
            seconds = min(MAX_BACKOFF_S, max(MIN_BACKOFF_S, reading.get("retry_after_s", FAILURE_BACKOFF_S)))
            if reading["reason"] in STRUCTURAL:
                # decisions/hqr-38-spec.md, A29: the provider answered; retry at the next cycle instead of the failure backoff.
                seconds = MIN_BACKOFF_S
            reading = dict(reading, failed_at=failed_at.isoformat(), retry_at=(failed_at + timedelta(seconds=seconds)).isoformat())
        readings[provider] = reading
        if cache is not None:
            cache[provider] = reading
    if clock:
        readings = revalidate(readings, clock(), max_age_s)
    return readings, queries
