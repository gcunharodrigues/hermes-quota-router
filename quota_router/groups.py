# Implements decisions/hqr-20-amendment.md, section 4 and AC-18/19; decisions/s3-plan.md, "Escopo";
# decisions/hqr-38-spec.md, D-28/D-29 ("Rede de segurança"): closed `fallback_providers` groups.
"""Closed Auto projections; never retain an unprojected document or a credential."""
from copy import deepcopy
import pickle

from .settings import EFFORTS, PROVIDER_MODELS, PROVIDERS, safe_model, safe_name
from .routes import defaults

FIELDS = ("provider", "model", "base_url", "api_mode", "reasoning_effort")
CONVERSATION = ("model.provider", "model.default", "model.base_url", "model.api_mode", "agent.reasoning_effort")
OPTIONS = "delegation.backends.model_map.options"
FORBIDDEN = ("api_key", "api", "key_env", "api_key_env", "context_length")
# decisions/hqr-38-spec.md, D-29: one safety net group per enrolled group, named apart from any route option name.
FALLBACK = "fallback_providers"
FALLBACK_PREFIX = "fallback:"
# Native entry fields (hermes_cli/fallback_config.py, agent/route_binding.py); credentials and effort never enter.
ENTRY_FIELDS = ("provider", "model", "base_url", "api_mode")


def fallback_group(role):
    return FALLBACK_PREFIX + role


def is_fallback(group):
    return isinstance(group, str) and group.startswith(FALLBACK_PREFIX)


def owner(group):
    """The conversation or route whose safety net a group holds; the group itself otherwise."""
    return group[len(FALLBACK_PREFIX):] if is_fallback(group) else group


def valid_chain(value):
    """Closed native chain: governed providers, their own model ids and at most the qualified D18 defaults."""
    if not isinstance(value, list):
        return False
    for entry in value:
        if not isinstance(entry, dict) or not {"provider", "model"} <= set(entry) <= set(ENTRY_FIELDS):
            return False
        provider, model = entry["provider"], entry["model"]
        if provider not in PROVIDERS or not safe_model(model) or not PROVIDER_MODELS[provider].match(model):
            return False
        native = defaults(provider)
        if any(key in entry and entry[key] not in ("", native.get(key)) for key in ("base_url", "api_mode")):
            return False
    return True


_ABSENT = object()


def _node(document, path):
    node = document
    for part in path.split('.'):
        if not isinstance(node, dict) or part not in node:
            return _ABSENT
        node = node[part]
    return node


def get(document, path):
    node = _node(document, path)
    return {"present": False} if node is _ABSENT else {"present": True, "value": deepcopy(node)}


def option(document, role):
    # Desempenho 2026-11-19: only the matching entry is copied, not the whole options list (about 1100 calls per cycle).
    options = _node(document, OPTIONS)
    matches = [o for o in options if isinstance(o, dict) and o.get("name") == role] if isinstance(options, list) else []
    return deepcopy(matches[0]) if len(matches) == 1 else None



# decisions/hqr-20-amendment.md, AC-18; decisions/s3-delivery.md, G7: aliases must not extend the write boundary.
def shared_boundary(document, role):
    """Reject shared YAML containers on a managed leaf's mutation path, including cycles."""
    fields = (FALLBACK,) if is_fallback(role) else FIELDS
    role = owner(role) if is_fallback(role) else role
    if role == 'conversation':
        leaves = [(FALLBACK,)] if fields == (FALLBACK,) else [tuple(key.split('.')) for key in CONVERSATION]
    else:
        options = document.get('delegation', {}).get('backends', {}).get('model_map', {}).get('options', [])
        if not isinstance(options, list):
            return False
        indexes = [i for i, value in enumerate(options) if isinstance(value, dict) and value.get('name') == role]
        leaves = [tuple(OPTIONS.split('.')) + (i, field) for i in indexes for field in fields]
    return aliased(document, leaves)


def _walk(value, ancestors, seen, prefixes=None, path=()):
    """Visit containers and anchored values as the alias check always did: a cycle is recorded, not entered.

    With `prefixes`, only children whose path is a prefix of some leaf are followed.
    """
    container = isinstance(value, (dict, list))
    anchored = getattr(getattr(value, 'anchor', None), 'value', None) is not None
    if not container and not anchored:
        return
    identity = id(value)
    seen[identity] = seen.get(identity, 0) + 1
    if identity in ancestors or not container:
        return
    ancestors.add(identity)
    for key, child in value.items() if isinstance(value, dict) else enumerate(value):
        if prefixes is None:
            _walk(child, ancestors, seen)
        elif path + (key,) in prefixes:
            _walk(child, ancestors, seen, prefixes, path + (key,))
    ancestors.discard(identity)


# Desempenho 2026-11-18: one cycle checked about 460 groups, each walking the whole 148 KB document. Reference counts
# do not depend on the group, so the last document's counts are kept while the very same object is checked again.
# Revisão da simplificação, F3: the memo fails closed. It also keeps the document's pickle, which records every shared
# reference, so a document changed in place after the count is counted again; a node the counts do not know (an equal
# copy put in place) is counted again too, and a node still unknown then counts as aliased instead of raising.
_COUNTS = (None, {}, None)


def _fingerprint(document):
    try:
        return pickle.dumps(document, pickle.HIGHEST_PROTOCOL)
    except Exception:
        return None


def _count(document):
    global _COUNTS
    counts = {}
    _walk(document, set(), counts)
    fingerprint = _fingerprint(document)
    # A document pickle cannot record is counted again on every call, as before the memo.
    _COUNTS = (document, counts, fingerprint) if fingerprint is not None else (None, {}, None)
    return counts


def aliased(document, leaves):
    """True when a container or anchored value on some leaf's path is reached more than once (an alias or a cycle).

    Same verdict as recording every path of every node and comparing each with each leaf.
    """
    prefixes = {leaf[:size] for leaf in leaves for size in range(len(leaf) + 1)}
    if not prefixes:
        return False
    memo = _COUNTS
    kept = memo[0] is document and _fingerprint(document) == memo[2]
    counts = memo[1] if kept else _count(document)
    on_path = {}
    _walk(document, set(), on_path, prefixes)
    if kept and not on_path.keys() <= counts.keys():
        counts = _count(document)
    return any(counts.get(identity, 2) > 1 for identity in on_path)



# decisions/s3-plan.md, R2/N2 and "Escopo": reject credentials, aliases, custom endpoints and conflicting effort overrides.
def preconditions(document, role, route_projections=()):
    if not isinstance(document, dict):
        return ["config"]
    if is_fallback(role):
        return _fallback_preconditions(document, role)
    try:
        if shared_boundary(document, role):
            return ['yaml_alias_crosses_group']
    except (AttributeError, TypeError, RecursionError):
        return ['config']
    # D18/R2: the native final overlay also affects Codex children; never enroll or write any affected group.
    # Only the field name may leave this check; an unknown non-string setting is not an empty opt-in.
    model = document.get('model')
    overlay = model.get('openai_runtime') if isinstance(model, dict) else None
    if overlay is not None and not (isinstance(overlay, str) and not overlay.strip()):
        return ['model.openai_runtime']
    if role == "conversation":
        node = document.get("model")
        if not isinstance(node, dict):
            return ["model"]
        errors = ["model." + key for key in (*FORBIDDEN, "model", "name") if key in node]
        overrides = get(document, "agent.reasoning_overrides").get("value")
        if isinstance(overrides, dict):
            # The native resolver accepts case-insensitive ids and provider-qualified ids.
            from .mapping import conversation_override
            if conversation_override(overrides):
                errors.append("agent.reasoning_overrides")
        prefix = "model."
    else:
        if not safe_name(role) or role == "cron":
            return ["role"]
        node = option(document, role)
        if node is None:
            return [OPTIONS]
        errors = [OPTIONS + "." + key for key in FORBIDDEN if key in node]
        prefix = OPTIONS + "."
    native = defaults(node.get("provider"))
    keys = CONVERSATION if role == 'conversation' else FIELDS
    # D18/D15: only validated journal cells can admit a partially written prior/target route.
    for projection in route_projections:
        validate_projection(role, projection)
    for index, key in ((2, "base_url"), (3, "api_mode")):
        value = node.get(key)
        allowed = [p[keys[index]].get('value') for p in route_projections]
        if value not in (None, "") and value != native.get(key) and value not in allowed:
            errors.append(prefix + key)
    for key, valid in (("provider", lambda v: v in PROVIDERS),
                       ("default" if role == "conversation" else "model", lambda v: safe_model(v) is not None),
                       ("reasoning_effort", lambda v: v in EFFORTS)):
        source = get(document, "agent").get("value", {}) if role == "conversation" and key == "reasoning_effort" else node
        if not isinstance(source, dict):
            errors.append("agent")
        elif key in source and source[key] is not None and not valid(source[key]):
            errors.append(("agent." if role == "conversation" and key == "reasoning_effort" else prefix) + key)
    return errors


# decisions/hqr-38-spec.md, D-29: same S3 gates (alias boundary, overlay, credentials); only the field name leaves.
def _fallback_preconditions(document, group):
    role = owner(group)
    try:
        if shared_boundary(document, group):
            return ['yaml_alias_crosses_group']
    except (AttributeError, TypeError, RecursionError):
        return ['config']
    model = document.get('model')
    overlay = model.get('openai_runtime') if isinstance(model, dict) else None
    if overlay is not None and not (isinstance(overlay, str) and not overlay.strip()):
        return ['model.openai_runtime']
    if role == "conversation":
        cell, field, errors = get(document, FALLBACK), FALLBACK, []
    else:
        if not safe_name(role) or role == "cron":
            return ["role"]
        node = option(document, role)
        if node is None:
            return [OPTIONS]
        errors = [OPTIONS + "." + key for key in FORBIDDEN if key in node]
        cell, field = get(node, FALLBACK), OPTIONS + "." + FALLBACK
    if cell["present"] and cell["value"] is not None and not valid_chain(cell["value"]):
        errors.append(field)
    return errors


def project(document, role, route_projections=()):
    if preconditions(document, role, route_projections):
        raise ValueError("Group preconditions failed")
    if is_fallback(role):
        source = document if owner(role) == "conversation" else option(document, owner(role))
        return {FALLBACK: get(source, FALLBACK)}
    if role == "conversation":
        return {path: get(document, path) for path in CONVERSATION}
    node = option(document, role)
    return {field: get(node, field) for field in FIELDS}


# D18: sync both wire fields to the selected native defaults instead of retaining the previous provider route.
def target(role, selection, baseline=None):
    if is_fallback(role):
        # decisions/hqr-38-spec.md, "Rede de segurança": an empty chain is written as [] only over a baseline that had the key.
        chain = selection.get("chain") if isinstance(selection, dict) else None
        if not valid_chain(chain) or any(set(entry) != {"provider", "model"} for entry in chain):
            raise ValueError("Invalid target")
        if chain or ((baseline or {}).get(FALLBACK) or {}).get("present"):
            return {FALLBACK: {"present": True, "value": deepcopy(chain)}}
        return {FALLBACK: {"present": False}}
    if selection.get("provider") not in PROVIDERS or not safe_model(selection.get("model")) or selection.get("effort") not in EFFORTS:
        raise ValueError("Invalid target")
    native = defaults(selection["provider"])
    values = (selection["provider"], selection["model"], native.get("base_url"), native.get("api_mode"), selection["effort"])
    return {key: {"present": False} if value is None else {"present": True, "value": value}
            for key, value in zip(CONVERSATION if role == "conversation" else FIELDS, values)}


def effective_fallback_errors(document, group, projection, allowed, *, prior=None):
    """SOL-05: qualify unowned native sources after projecting a target; return field names, never refused values.

    An absent route key inherits delegation.fallback_providers; [] suppresses inheritance.
    At the root fallback_model is always appended, even to []; neither unowned source is written.
    """
    validate_projection(group, projection)
    if not is_fallback(group) or not valid_chain(allowed):
        raise ValueError("Invalid safety net qualification")
    cell = projection[FALLBACK]
    sources = []
    if owner(group) == "conversation":
        # The root legacy fallback is always appended: deleting a proven managed chain cannot expose a new source.
        clearing_managed = not allowed and not cell.get('value') and prior and prior[FALLBACK].get('value')
        if not clearing_managed:
            sources.append(("fallback_model", document.get("fallback_model")))
    elif not cell["present"] or cell.get("value") is None:
        sources.append(("delegation." + FALLBACK, get(document, "delegation." + FALLBACK).get("value")))
    eligible = {(entry["provider"], entry["model"]) for entry in allowed}
    errors = []
    for field, value in sources:
        if value is None or value == [] or value == {}:
            continue
        chain = [value] if isinstance(value, dict) else value
        if not valid_chain(chain) or any((entry["provider"], entry["model"]) not in eligible for entry in chain):
            errors.append(field)
    return errors


# D18/AC-19: retained records admit only empty fields or the recorded provider's qualified public defaults.
def validate_projection(role, projection):
    if is_fallback(role):
        name = owner(role)
        if not safe_name(name) or name == 'cron' or not isinstance(projection, dict) or set(projection) != {FALLBACK}:
            raise ValueError('Invalid closed projection')
        cell = projection[FALLBACK]
        if not isinstance(cell, dict) or type(cell.get('present')) is not bool:
            raise ValueError('Invalid presence marker')
        if set(cell) != ({'present', 'value'} if cell['present'] else {'present'}):
            raise ValueError('Invalid projection cell')
        if cell['present'] and cell['value'] is not None and not valid_chain(cell['value']):
            raise ValueError('Invalid projected value')
        return projection
    keys = CONVERSATION if role == 'conversation' else FIELDS
    if not safe_name(role) or role == 'cron' or not isinstance(projection, dict) or set(projection) != set(keys):
        raise ValueError('Invalid closed projection')
    for key, cell in projection.items():
        if not isinstance(cell, dict) or type(cell.get('present')) is not bool:
            raise ValueError('Invalid presence marker')
        if set(cell) != ({'present', 'value'} if cell['present'] else {'present'}):
            raise ValueError('Invalid projection cell')
        if not cell['present'] or cell['value'] is None:
            continue
        value = cell['value']
        field = key.rsplit('.', 1)[-1]
        valid = (value in PROVIDERS if field == 'provider' else safe_model(value) is not None if field in ('model', 'default')
                 else isinstance(value, str) and value in EFFORTS if field == 'reasoning_effort'
                 else value == '' or value == defaults(projection[keys[0]].get('value')).get(field))
        if not valid:
            raise ValueError('Invalid projected value')
    return projection



# decisions/hqr-20-amendment.md, D6; decisions/s3-plan.md, O3: native list writes preserve non-projected fields, with a residual race.
def changes(document, role, projection):
    validate_projection(role, projection)
    """Read-modify-write the whole options list; only its five projected fields change."""
    if role == fallback_group("conversation"):
        cell = projection[FALLBACK]
        return ({FALLBACK: deepcopy(cell["value"])}, ()) if cell["present"] else ({}, (FALLBACK,))
    if role == "conversation":
        return ({k: deepcopy(v["value"]) for k, v in projection.items() if v["present"]},
                tuple(k for k, v in projection.items() if not v["present"]))
    options = get(document, OPTIONS)["value"]
    node = next(o for o in options if isinstance(o, dict) and o.get("name") == owner(role))
    for key, value in projection.items():
        if value["present"]:
            node[key] = deepcopy(value["value"])
        else:
            node.pop(key, None)
    return {OPTIONS: options}, ()
