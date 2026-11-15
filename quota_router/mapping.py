"""Equivalence map proposal by role and variant (HQR-20 amendment, section 15; decision D5).

The proposal is never applied; only a map approved by Guilherme (`roles` setting, `config approve-map`) makes a decision actionable.
"""

VARIANTS = ("base", "fable", "astra", "fable+astra")


def model_gate(model):
    """Reason a target model cannot be chosen in S2, or None: Fable's own window and Astra's catalog are not visible."""
    name = (model or "").lower()
    if "fable" in name:
        return "model_not_eligible:fable"
    if "astra" in name:
        return "model_not_eligible:astra"
    return None
CONVERSATION_CODEX = {"model": "gpt-6.1-sol", "effort": "xhigh"}
CODEX_STRONG = "gpt-6.1-sol"
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
