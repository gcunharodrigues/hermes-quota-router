"""Plugin settings: schema, defaults and validation (HQR-20 amendment, section 13).

Values live in the plugin's native subtree and are read and written only through ctx.get_config and ctx.set_config.
An invalid saved value is never echoed: diagnostics carry only its type and the validation reason.
"""
import re

PROVIDERS = ("openai-codex", "anthropic")

DEFAULTS = {
    "mode": "off",
    "consumers.subagents": True,
    "consumers.cron": True,
    "consumers.conversation": True,
    "conversation.policy": "principal_first",
    "principal": "openai-codex",
    "credits.openai-codex": True,
    "credits.anthropic": False,
    "credits.order": "after_subscriptions",
    "models.fable": False,
    "models.astra": False,
    "limits.session_block_pct": 95,
    "limits.week_block_pct": 100,
    "limits.reading_max_age_s": 60,
    "limits.hysteresis_pct": 10,
    "roles": {},
}

CHOICES = {
    "mode": ("off", "observe", "auto"),
    "conversation.policy": ("principal_first", "pacing"),
    "principal": PROVIDERS,
    "credits.order": ("after_subscriptions",),
}

RANGES = {
    "limits.session_block_pct": (1, 100),
    "limits.week_block_pct": (1, 100),
    "limits.reading_max_age_s": (1, 3600),
    "limits.hysteresis_pct": (0, 100),
}

# Hermes' canonical effort ladder (agent/reasoning_effort.py EFFORT_LADDER).
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
# Model ids of the two governed providers only; URLs, paths and key-shaped strings never pass.
MODEL = re.compile(r"^(gpt|claude|codex|o[0-9])[A-Za-z0-9._-]{0,63}$")
SECRETISH = re.compile(r"^(sk[-_]|ghp_|gho_|github_pat_|xox[abpr]-|AKIA|AIza)|@")
PROVIDER_MODELS = {"openai-codex": re.compile(r"^(gpt|codex|o[0-9])"), "anthropic": re.compile(r"^claude")}

_TRUE = ("true", "on", "yes", "1")
_FALSE = ("false", "off", "no", "0")


def safe_name(value):
    return value if isinstance(value, str) and NAME.match(value) and not SECRETISH.search(value) else None


def safe_model(value):
    return value if isinstance(value, str) and MODEL.match(value) and not SECRETISH.search(value) else None


def _valid_roles(value):
    if not isinstance(value, dict):
        return False, "expected a mapping of role to provider pairs"
    for role, pair in value.items():
        if not safe_name(role) or not isinstance(pair, dict) or set(pair) != set(PROVIDERS):
            return False, "each role needs both providers"
        for provider, entry in pair.items():
            if not isinstance(entry, dict) or set(entry) != {"model", "effort"}:
                return False, "each provider entry needs model and effort"
            if not safe_model(entry["model"]) or entry["effort"] not in EFFORTS:
                return False, "invalid model or effort"
            if not PROVIDER_MODELS[provider].match(entry["model"]):
                return False, "model does not belong to its provider"
    return True, value


def validate(key, value):
    """Return (True, normalized) or (False, reason) for one setting."""
    if key not in DEFAULTS:
        return False, "unknown setting"
    default = DEFAULTS[key]
    if key == "roles":
        return _valid_roles(value)
    if isinstance(default, bool):
        if isinstance(value, bool):
            return True, value
        if isinstance(value, str) and value.strip().lower() in _TRUE + _FALSE:
            return True, value.strip().lower() in _TRUE
        return False, "expected true or false"
    if key in RANGES:
        low, high = RANGES[key]
        number = None
        if isinstance(value, int) and not isinstance(value, bool):
            number = value
        elif isinstance(value, str) and re.fullmatch(r"\d{1,6}", value.strip()):
            number = int(value.strip())
        if number is None or not low <= number <= high:
            return False, f"expected an integer from {low} to {high}"
        return True, number
    if isinstance(value, str) and value.strip() in CHOICES[key]:
        return True, value.strip()
    return False, "expected one of " + ", ".join(CHOICES[key])


def load(read):
    """Effective settings from saved values; an invalid saved value is reported by type and replaced by its default.

    `read(key, default)` returns the saved value or the default; callers mark decisions incomplete while invalid is not empty.
    """
    effective, invalid = {}, {}
    for key, default in DEFAULTS.items():
        saved = read(key, default)
        ok, normalized = validate(key, saved)
        if ok:
            effective[key] = normalized
        else:
            effective[key] = dict(default) if isinstance(default, dict) else default
            invalid[key] = {"saved_type": type(saved).__name__, "reason": normalized}
    return effective, invalid
