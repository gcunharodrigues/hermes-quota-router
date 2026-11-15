"""Native quota readings (HQR-20 amendment, section 14; AC-16).

Uses only the host reader `agent.account_usage.fetch_account_usage(provider, read_only=True)`.
The plugin never sees tokens; from the Codex `raw` body it keeps only an allowlist of credit and availability fields.
Any contract drift (unknown window label, duplicate window, provider mismatch, malformed shape) becomes an unknown reading.
"""
from datetime import datetime, timezone
import math
import re

SESSION_S = 18000
WEEK_S = 604800

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


def native_importer():
    """Return the native reader, or None when this process has no Hermes host."""
    try:
        from agent.account_usage import fetch_account_usage
    except Exception:
        return None
    return lambda provider: fetch_account_usage(provider, read_only=True)


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


def _codex_credits(raw):
    credits = raw.get("credits")
    if not isinstance(credits, dict):
        return {"visible": False}
    return {"visible": True, "has_credits": _flag(credits, "has_credits"), "unlimited": _flag(credits, "unlimited"),
            "balance_positive": _positive_balance(credits.get("balance")),
            "overage_limit_reached": _flag(credits, "overage_limit_reached"),
            "spend_reached": _flag(raw.get("spend_control"), "reached")}


def _codex_durations(raw):
    """Durations the Codex response publishes (`limit_window_seconds`), one per present window slot, in response order.

    The host emits one window per slot that carries usage, in the same order; any slot it skipped makes the lists differ in length.
    """
    rate_limit = raw.get("rate_limit")
    found = []
    for key in ("primary_window", "secondary_window"):
        window = rate_limit.get(key) if isinstance(rate_limit, dict) else None
        if not window:
            continue
        seconds = window.get("limit_window_seconds") if isinstance(window, dict) else None
        found.append(seconds if isinstance(seconds, int) and not isinstance(seconds, bool) else None)
    return found


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
            return _unknown(provider, "unknown_window_label", stamp)
        kind, duration, family = LABELS[label]
        if getattr(window, "scope", None) != SCOPES[kind]:
            return _unknown(provider, "scope_mismatch", stamp)
        if (kind, family) in seen:
            return _unknown(provider, "conflicting_windows", stamp)
        seen.add((kind, family))
        used, reset = getattr(window, "used_percent", None), getattr(window, "reset_at", None)
        if isinstance(used, bool) or not isinstance(used, (int, float)) or not 0 <= used <= 100 or used != used:
            return _unknown(provider, "malformed_window", stamp)
        if not _aware(reset):
            return _unknown(provider, "malformed_window", stamp)
        if reset <= now:
            return _unknown(provider, "reset_passed", stamp)
        windows.append({"kind": kind, "family": family, "used_pct": used, "used": used / 100,
                        "reset_at": reset.astimezone(timezone.utc).isoformat(), "duration_s": duration})
    if not any(w["kind"] == "week" for w in windows):
        return _unknown(provider, "no_week_window", stamp)
    raw = getattr(snapshot, "raw", None)
    raw = raw if isinstance(raw, dict) else {}
    if provider == "openai-codex":
        # The host labels a Codex window with a missing or unknown duration by position; such a label is not evidence.
        published = _codex_durations(raw)
        if published != [w["duration_s"] for w in windows]:
            return _unknown(provider, "window_duration_unqualified", stamp)
    source = getattr(snapshot, "source", None)
    return {"provider": provider, "state": "ok", "reason": None, "source": source if isinstance(source, str) and SOURCE.match(source) else None,
            "fetched_at": stamp, "age_s": age, "windows": windows,
            "credits": _codex_credits(raw) if provider == "openai-codex" else {"visible": False},
            "astra_available": _astra(raw) if provider == "openai-codex" else None,
            "upstream": _upstream(raw) if provider == "openai-codex" else {"allowed": None, "limit_reached": None}}


def normalize(provider, snapshot, now, max_age_s):
    """One reading with windows as fractions, or an unknown state with a reason; never free capacity."""
    if snapshot is None:
        return _unknown(provider, "no_snapshot")
    try:
        return _normalize(provider, snapshot, now, max_age_s)
    except Exception:
        return _unknown(provider, "malformed_snapshot")


def revalidate(readings, now, max_age_s):
    """Readings judged again at one decision time: an expired or reset-crossed reading becomes unknown."""
    result = {}
    for provider, reading in readings.items():
        if reading["state"] != "ok":
            result[provider] = reading
            continue
        valid = _still_valid(reading, now, max_age_s)
        if valid is not None:
            result[provider] = valid
            continue
        age = (now - datetime.fromisoformat(reading["fetched_at"])).total_seconds()
        reason = "future_reading" if age < 0 else "stale_reading" if age > max_age_s else "reset_passed"
        result[provider] = _unknown(provider, reason, reading["fetched_at"])
    return result


def _still_valid(reading, now, max_age_s):
    if reading["state"] != "ok":
        return None
    age = (now - datetime.fromisoformat(reading["fetched_at"])).total_seconds()
    if not 0 <= age <= max_age_s:
        return None
    if any(datetime.fromisoformat(w["reset_at"]) <= now for w in reading["windows"]):
        return None
    return dict(reading, age_s=age)


def collect(providers, now, max_age_s, reader=None, cache=None, importer=None, clock=None):
    """Read each provider once per freshness window; returns (readings, queries issued).

    `now` validates cache hits; each fresh reading is judged with `clock()` sampled after its fetch.
    """
    if reader is None:
        reader = (importer or native_importer)()
    readings, queries = {}, 0
    for provider in providers:
        cached = (cache or {}).get(provider)
        reused = _still_valid(cached, now, max_age_s) if cached else None
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
            readings[provider] = _unknown(provider, "reader_error")
            continue
        readings[provider] = normalize(provider, snapshot, clock() if clock else now, max_age_s)
        if cache is not None:
            cache[provider] = readings[provider]
    if clock:
        readings = revalidate(readings, clock(), max_age_s)
    return readings, queries
