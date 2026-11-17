# Implements decisions/hqr-20-amendment.md, sections 3/4 and D12/D13; decisions/s3-plan.md, "Cron".
"""Read-only inventory of the profile routes the Auto would change (HQR-20 amendment, sections 3 and 4).

Reads the raw profile document with `hermes_cli.config_backend.read_config_doc` (open and parse only) and the cron jobs file directly.
It never calls native loaders that create folders, back up or repair files (`load_config*`, `read_raw_config`, `load_jobs`),
and it never returns endpoints, keys, job names or prompts.
"""
import json
import re

from .settings import EFFORTS, SECRETISH, safe_model, safe_name

PIN_KEYS = ("provider", "model", "base_url")
NOT_GOVERNED = ("auxiliary", "retries", "fallbacks", "calls_in_flight", "managed_sessions_created_before_decision")
JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ROUTE_EFFORTS = EFFORTS
PROVIDER = re.compile(r"^[a-z0-9-]{1,32}$")


def _clean(value, pattern):
    return value if isinstance(value, str) and pattern.match(value) and not SECRETISH.search(value) else None


def read_jobs_file(path):
    """Jobs list from a native jobs file without changing it; [] when absent, None when unreadable or malformed."""
    try:
        with open(path, "rb") as handle:
            data = json.loads(handle.read().decode("utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if isinstance(data, dict):
        data = data.get("jobs")
    return data if isinstance(data, list) else None



# decisions/hqr-20-amendment.md, AC-17: raw parsing avoids native bootstrap, backup and job-repair side effects.
def native_sources():
    """(profile config, cron jobs) from the host, or None for each source outside a Hermes process."""
    try:
        from hermes_cli.config import get_config_path
        from hermes_cli.config_backend import read_config_doc
        path = get_config_path()
    except Exception:
        return None, None
    try:
        document = read_config_doc(path)
        config = {} if document is None else document if isinstance(document, dict) else None
    except FileNotFoundError:
        config = {}
    except Exception:
        config = None
    return config, read_jobs_file(path.parent / "cron" / "jobs.json")


def native_profile():
    try:
        from hermes_cli.profiles import get_active_profile_name
        return safe_name(get_active_profile_name()) or "unknown"
    except Exception:
        return "unknown"


def _get(mapping, key):
    value = mapping.get(key) if isinstance(mapping, dict) else None
    return value if isinstance(value, dict) else {}


def _route(provider, model, effort):
    return {"provider": _clean(provider, PROVIDER), "model": safe_model(model), "effort": effort if effort in ROUTE_EFFORTS else None}


def read(config, jobs):
    if not isinstance(config, dict):
        return {"state": "unavailable", "not_governed": list(NOT_GOVERNED)}
    model, agent, delegation = _get(config, "model"), _get(config, "agent"), _get(config, "delegation")
    model_map = _get(_get(delegation, "backends"), "model_map")
    options = model_map.get("options") if isinstance(model_map.get("options"), list) else []
    default = _route(delegation.get("provider"), delegation.get("model"), delegation.get("reasoning_effort"))
    conversation = _route(model.get("provider"), model.get("default") or model.get("model"), agent.get("reasoning_effort"))
    routes = []
    for index, option in enumerate(options, 1):
        if not isinstance(option, dict):
            continue
        route = _route(option.get("provider"), option.get("model"), option.get("reasoning_effort"))
        declared = {"provider": option.get("provider"), "model": option.get("model"), "effort": option.get("reasoning_effort")}
        invalid = [k for k in route if route[k] is None and declared[k] not in (None, "")]
        inherited = [k for k in route if route[k] is None and k not in invalid and default[k] is not None]
        resolved = {k: default[k] if k in inherited else route[k] for k in route}
        routes.append(dict(resolved, name=safe_name(option.get("name")) or f"invalid-{index}", inherited=inherited, invalid=invalid))
    cron_cfg = _get(config, "cron")
    cron = dict(_route(cron_cfg.get("model_provider"), cron_cfg.get("model"), None), pinned=0, unpinned=0, partial_pins=[],
                jobs_state="ok" if isinstance(jobs, list) else "unavailable")
    for index, job in enumerate(jobs if isinstance(jobs, list) else [], 1):
        if not isinstance(job, dict):
            continue
        present = [k for k in PIN_KEYS if isinstance(job.get(k), str) and job[k].strip()]
        if not present:
            cron["unpinned"] += 1
        elif "provider" in present and "model" in present:
            cron["pinned"] += 1
        else:
            job_id = _clean(job.get("id"), JOB_ID) or f"job-{index}"
            cron["partial_pins"].append({"job": job_id, "missing": [k for k in ("provider", "model") if k not in present]})
    cron["globals_writable"] = cron["jobs_state"] == "ok" and not cron["partial_pins"]
    return {"state": "ok", "conversation": conversation, "delegation_default": default, "routes": routes, "cron": cron,
            "not_governed": list(NOT_GOVERNED)}


def _effort(value):
    """Native parsing on Hermes; closed offline representation when the host is unavailable."""
    try:
        from hermes_constants import parse_reasoning_effort
    except ImportError:
        pass
    else:
        try:
            return _closed_effort(parse_reasoning_effort(value))
        except Exception:
            return None
    if value is False:
        return 'none'
    if isinstance(value, dict):
        if value.get('enabled', True) is False:
            return 'none'
        value = value.get('effort')
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if value in ('false', 'disabled'):
        return 'none'
    return value if value in EFFORTS else None


def _closed_effort(parsed):
    if not isinstance(parsed, dict):
        return None
    if parsed.get('enabled') is False:
        return 'none'
    effort = parsed.get('effort')
    return effort if isinstance(effort, str) and effort in EFFORTS else None


def _override_effort(model, overrides):
    try:
        from hermes_constants import resolve_per_model_reasoning_effort
    except ImportError:
        pass
    else:
        try:
            return _closed_effort(resolve_per_model_reasoning_effort(model, overrides))
        except Exception:
            return None
    # Offline inventory has no qualified Hermes resolver; this fallback is not Auto admission.
    if not isinstance(model, str):
        return None
    exact = _effort(overrides.get(model))
    if exact is not None:
        return exact
    canonical = model.rsplit('/', 1)[-1].replace('.', '-')
    for key, raw in overrides.items():
        if isinstance(key, str) and key.rsplit('/', 1)[-1].replace('.', '-') == canonical:
            parsed = _effort(raw)
            if parsed is not None:
                return parsed
    return None


def cron_origins(config, jobs):
    """Per-field cron inheritance, not a cron write group (D12, D13)."""
    config = config if isinstance(config, dict) else {}
    conversation = _get(config, "model")
    cron, agent = _get(config, "cron"), _get(config, "agent")
    overrides = _get(agent, "reasoning_overrides")

    # decisions/hqr-20-amendment.md, D12/D13; decisions/s3-plan.md, "Cron": resolve model/provider independently.
    def origin(job):
        model = job.get("model") or cron.get("model") or conversation.get("default")
        provider = job.get("provider") or cron.get("model_provider") or conversation.get("provider")
        model_source = "job" if job.get("model") else "cron.model" if cron.get("model") else "conversation"
        provider_source = "job" if job.get("provider") else "cron.model_provider" if cron.get("model_provider") else "conversation"
        # decisions/s3-plan.md, N5: valid job effort wins, then the effective model override, then conversation effort.
        pin = _effort(job.get("reasoning_effort"))
        override = _override_effort(model, overrides)
        effort, effort_source = (pin, "job") if pin is not None else (
            (override, "agent.reasoning_overrides") if override is not None else
            (_effort(agent.get("reasoning_effort")), "agent.reasoning_effort"))
        return {"model": {"value": safe_model(model), "origin": model_source},
                "provider": {"value": _clean(provider, PROVIDER), "origin": provider_source},
                "effort": {"value": effort if isinstance(effort, str) and effort in EFFORTS else None, "origin": effort_source},
                "partial": model_source != provider_source.replace("cron.model_provider", "cron.model")}

    rows = []
    for index, job in enumerate(jobs if isinstance(jobs, list) else [], 1):
        if isinstance(job, dict):
            rows.append(dict(origin(job), job=_clean(job.get("id"), JOB_ID) or f"job-{index}",
                             pinned=any(job.get(k) for k in PIN_KEYS)))
    return {"default": origin({}), "jobs": rows, "jobs_state": "ok" if isinstance(jobs, list) else "unavailable",
            "consumers.cron": "sem efeito; cron segue a conversa nos campos sem padrão/pin; fixe provider, modelo e esforço no job"}
