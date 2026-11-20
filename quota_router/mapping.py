# Implements decisions/hqr-20-amendment.md, section 15 and D5/D9/D12; decisions/s3-plan.md, "Mapa aprovado";
# decisions/aux-plan.md, "Mapa por tarefa", D-AUXP-1/7/8.
"""Equivalence map proposal by role and variant (HQR-20 amendment, section 15; decision D5).

The proposal is never applied; only an operator-approved map (`roles` setting, `config approve-map`) makes a decision actionable.
"""

from copy import deepcopy
import importlib
import json
import os
import sys

VARIANTS = ("base", "fable", "astra", "fable+astra")

# Approved map data: decisions/s3-plan.md, "Mapa aprovado"; decisions/hqr-20-amendment.md, D9.
_BASE_ROWS = {
    "conversation": ("sol", "xhigh", "opus", "high"),
    "general": ("sol", "medium", "opus", "medium"),
    "analysis": ("sol", "high", "opus", "high"),
    "strategy": ("sol", "xhigh", "opus", "high"),
    "research": ("sol", "high", "opus", "high"),
    "coding": ("sol", "xhigh", "opus", "high"),
    "review": ("sol", "xhigh", "opus", "high"),
    "deep": ("sol", "max", "opus", "xhigh"),
    "routine": ("terra", "medium", "sonnet", "high"),
    "triage": ("terra", "low", "sonnet", "medium"),
    "extract": ("luna", "high", "haiku", "high"),
}
_MODEL_IDS = {"sol": "gpt-6.2-sol", "terra": "gpt-6.1-terra", "luna": "gpt-6-luna",
              "opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}


# decisions/aux-plan.md, "Mapa por tarefa", D-AUXP-1/7/8: proposal only; approval is persisted separately.
_AUXILIARY_ROWS = {
    "title_generation": ("luna", "haiku", "low"),
    "profile_describer": ("luna", "haiku", "low"),
    "tts_audio_tags": ("luna", "haiku", "low"),
    "compression": ("terra", "sonnet", "medium"),
    "background_review": ("terra", "sonnet", "medium"),
    "kanban_decomposer": ("terra", "sonnet", "medium"),
    "approval": ("terra", "sonnet", "low"),
    "goal_judge": ("terra", "sonnet", "low"),
    "monitor": ("terra", "sonnet", "low"),
    "triage_specifier": ("terra", "sonnet", "low"),
    "voice_chat": ("terra", "sonnet", "low"),
}


def approved_auxiliary():
    """Return an independent proposal; absent effort on Claude approval means remove the key, not null."""
    result = {task: {"openai-codex": {"model": _MODEL_IDS[c], "effort": effort},
                     "anthropic": {"model": _MODEL_IDS[a], "effort": effort}}
              for task, (c, a, effort) in _AUXILIARY_ROWS.items()}
    del result["approval"]["anthropic"]["effort"]
    return result


def approved_base():
    result = {role: {"openai-codex": {"model": _MODEL_IDS[c], "effort": ce},
                     "anthropic": {"model": _MODEL_IDS[a], "effort": ae}} for role, (c, ce, a, ae) in _BASE_ROWS.items()}
    result["cron"] = {"follows": "conversation"}
    return deepcopy(result)



# decisions/s3-plan.md, "Mapa aprovado"; docs/compatibility.md, "Catálogo nativo models.dev na S3": unknown is not absent.
def effective_map(proposal, settings):
    """D18/D9: the approved settings are the map in effect, not a fresh S2 equivalence proposal."""
    approved = settings['roles']
    if not approved:
        return proposal
    return {'status': 'approved', 'source': 'settings.roles', 'effective_variant': 'base',
            'label': 'base' if approved == approved_base() else 'approved',
            'variants': {'base': deepcopy({role: pair for role, pair in approved.items() if role != 'cron'})},
            'cron': {'follows': 'conversation'}, 'notes': []}


def catalog_gate(provider, model, catalogs):
    blocked = model_gate(model)
    if blocked:
        return blocked
    catalog = catalogs.get(provider)
    return "model_absent_from_catalog" if catalog is not None and model not in catalog else None


def _catalogs(registry, provider_map):
    catalogs = {}
    for provider in ("openai-codex", "anthropic"):
        entry = registry.get(provider_map.get(provider))
        models = entry.get("models") if isinstance(entry, dict) else None
        if isinstance(models, dict) and models and all(isinstance(model, str) for model in models):
            catalogs[provider] = list(models)
    return catalogs


# Desempenho 2026-11-18: the models.dev cache file has about 7 MB; when the host has not loaded it in memory, every
# role decision parsed it again (several seconds per cycle). One parse is kept while the file's stat is unchanged.
# Revisão da simplificação, F5: only the extracted catalogs are kept, keyed by the file stamp and the provider map.
_CATALOG_FILE = (None, None)


def _file_catalogs(path, provider_map):
    global _CATALOG_FILE
    info = os.stat(path)
    key = (str(path), (info.st_mtime_ns, info.st_size, info.st_ino),
           tuple(provider_map.get(provider) for provider in ("openai-codex", "anthropic")))
    if _CATALOG_FILE[0] != key:
        with open(path, 'r', encoding='utf-8-sig') as handle:
            registry = json.load(handle)
        _CATALOG_FILE = (key, _catalogs(registry, provider_map) if isinstance(registry, dict) else {})
    return _CATALOG_FILE[1]


def native_catalogs():
    # docs/compatibility.md, "Catálogo nativo models.dev na S3": held public metadata is not account availability.
    try:
        module = sys.modules.get("agent.models_dev")
        if module is None:
            module = importlib.import_module("agent.models_dev")
        registry = getattr(module, "_models_dev_cache", None)
        provider_map = module.PROVIDER_TO_MODELS_DEV
        if not isinstance(provider_map, dict):
            return {}
        if not isinstance(registry, dict) or not registry:
            # decisions/hqr-20-amendment.md, AC-17: native cache loaders repair files; use only the path helper and read.
            return {provider: list(models) for provider, models in _file_catalogs(module._get_cache_path(), provider_map).items()}
    except Exception:
        return {}
    return _catalogs(registry, provider_map)


def conversation_override(overrides):
    def canonical(value):
        return value.rsplit('/', 1)[-1].lower().replace('.', '-')
    models = {canonical(m) for m in ("gpt-6.2-sol", "gpt-6.1-sol", "claude-opus-5-5")}
    return any(isinstance(key, str) and canonical(key) in models for key in overrides)




# decisions/hqr-20-amendment.md, section 17/D9: Fable/Astra variants remain unapproved, even if discovered.
def model_gate(model):
    """Reason a target model cannot be chosen in S2, or None: Fable's own window and Astra's catalog are not visible."""
    name = (model or "").lower()
    if "fable" in name:
        return "model_not_eligible:fable"
    if "astra" in name:
        return "model_not_eligible:astra"
    return None
CONVERSATION_CODEX = {"model": "gpt-6.2-sol", "effort": "xhigh"}
CODEX_STRONG = "gpt-6.2-sol"
CODEX_STANDARD = "gpt-6.1-terra"
CLAUDE_STRONG = "claude-opus-5-5"
CLAUDE_STANDARD = "claude-sonnet-5-5"
FABLE = "claude-fable-5-2"
ASTRA = "gpt-6-astra"
STRONG_EFFORTS = ("high", "xhigh", "max", "ultra")


def _strong(model, effort):
    model = (model or "").lower()
    return any(tag in model for tag in ("sol", "opus", "fable", "astra")) or effort in STRONG_EFFORTS


def _pair(variant, provider, model, effort, strong):
    fable, astra = "fable" in variant, "astra" in variant
    codex = model if provider == "openai-codex" and model else (CODEX_STRONG if strong else CODEX_STANDARD)
    claude = model if provider == "anthropic" and model else (CLAUDE_STRONG if strong else CLAUDE_STANDARD)
    if strong and fable:
        claude = FABLE
    if strong and astra:
        codex = ASTRA
    effort = effort or ("xhigh" if strong else "medium")
    return {"openai-codex": {"model": codex, "effort": effort}, "anthropic": {"model": claude, "effort": effort}}


def roles(inventory):
    """Role -> (provider, model, effort) after inheritance; the conversation's Codex side is bound to sol xhigh."""
    conversation = inventory.get("conversation", {})
    found = {"conversation": ("openai-codex", CONVERSATION_CODEX["model"], CONVERSATION_CODEX["effort"])}
    for route in inventory.get("routes", []):
        found[route["name"]] = (route["provider"], route["model"], route["effort"])
    cron = inventory.get("cron", {})
    found["cron"] = (cron.get("provider") or conversation.get("provider"), cron.get("model") or conversation.get("model"),
                     conversation.get("effort"))
    return found


def propose(inventory, readings, settings):
    if inventory.get("state") != "ok":
        return {"status": "inventory_unavailable", "variants": {}, "effective_variant": None, "notes": []}
    variants = {}
    for variant in VARIANTS:
        table = {}
        for role, (provider, model, effort) in roles(inventory).items():
            pair = _pair(variant, provider, model, effort, _strong(model, effort))
            if role == "conversation":
                pair["openai-codex"] = dict(CONVERSATION_CODEX)
                pair["anthropic"]["effort"] = CONVERSATION_CODEX["effort"]
            table[role] = pair
        variants[variant] = table
    notes, fable, astra = [], settings["models.fable"], settings["models.astra"]
    if fable:
        notes.append("fable_window_not_visible")
        fable = False
    if astra:
        # Section 15 also requires the account catalog; the native catalog needs the token, which the plugin never handles.
        notes.append("astra_catalog_not_verifiable_by_plugin")
        if (readings.get("openai-codex") or {}).get("astra_available") is not True:
            notes.append("astra_unavailable")
        astra = False
    effective = {(False, False): "base", (True, False): "fable", (False, True): "astra", (True, True): "fable+astra"}[(fable, astra)]
    return {"status": "proposal_not_approved", "variants": variants, "effective_variant": effective, "notes": notes}
