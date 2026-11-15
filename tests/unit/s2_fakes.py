"""Synthetic native snapshots and settings for S2 tests; never real quota data."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
WEEK = 604800


@dataclass(frozen=True)
class Window:
    label: str
    used_percent: Optional[float] = None
    reset_at: Optional[datetime] = None
    detail: Optional[str] = None
    scope: str = "account"


@dataclass(frozen=True)
class Snapshot:
    provider: str
    source: str
    fetched_at: datetime
    windows: tuple = ()
    details: tuple = ()
    unavailable_reason: Optional[str] = None
    raw: Optional[dict] = None
    plan: Optional[str] = None


def codex_rate_limit(*seconds):
    """Native Codex `rate_limit` windows carrying `limit_window_seconds`, in response order."""
    keys = ("primary_window", "secondary_window")
    return {key: {"limit_window_seconds": value} for key, value in zip(keys, seconds)}


def codex(week_used, *, week_reset_h=72, session_used=None, credits=None, astra=None, fetched_at=NOW, allowed=None,
          spend_reached=False):
    windows = []
    if session_used is not None:
        windows.append(Window("Session", session_used, NOW + timedelta(hours=2)))
    windows.append(Window("Weekly", week_used, NOW + timedelta(hours=week_reset_h)))
    raw = {"rate_limit": dict(codex_rate_limit(*(18000 if w.label == "Session" else WEEK for w in windows)),
                              allowed=week_used < 100 if allowed is None else allowed, limit_reached=week_used >= 100)}
    if credits is not None:
        raw["credits"] = credits
        if spend_reached is not None:
            raw["spend_control"] = {"reached": spend_reached}
    if astra is not None:
        raw["model_usage"] = {"gpt-6-astra": {"available": astra}}
    return Snapshot("openai-codex", "usage_api", fetched_at, tuple(windows), raw=raw)


def claude(week_used, *, week_reset_h=120, session_used=None, fetched_at=NOW, opus_used=None):
    windows = []
    if session_used is not None:
        windows.append(Window("Current session", session_used, NOW + timedelta(hours=3)))
    windows.append(Window("Current week", week_used, NOW + timedelta(hours=week_reset_h)))
    if opus_used is not None:
        windows.append(Window("Opus week", opus_used, NOW + timedelta(hours=week_reset_h), scope="model"))
    return Snapshot("anthropic", "oauth_usage_api", fetched_at, tuple(windows))


CREDITS_OK = {"has_credits": True, "unlimited": False, "balance": "12.50", "overage_limit_reached": False}
CREDITS_EMPTY = {"has_credits": False, "unlimited": False, "balance": "0", "overage_limit_reached": False}


def reader_for(**snapshots):
    calls = []

    def reader(provider):
        calls.append(provider)
        value = snapshots.get(provider.replace("-", "_"))
        if isinstance(value, Exception):
            raise value
        return value

    reader.calls = calls
    return reader


def settings(overrides=None):
    from quota_router.settings import DEFAULTS
    values = dict(DEFAULTS)
    values.update(overrides or {})
    return values
