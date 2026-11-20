# Implements decisions/aux-plan.md, "Projeção fechada por grupo auxiliar", AUXP-03 and D-AUXP-2.
"""Closed auxiliary projections, independent of today's map, catalogs and plugin registry during recovery."""
from copy import deepcopy

from .groups import FIELDS, aliased, get
from .settings import EFFORTS, PROVIDERS, safe_model, safe_name

PREFIX = 'aux:'


# decisions/aux-plan.md, AUXP-03/H21: inspect only an already-loaded manager for the active home.
def native_registry(home=None):
    import sys
    from pathlib import Path
    unavailable = {'ok': False, 'reason': 'plugin_registry_unavailable', 'tasks': {}}
    try:
        module = sys.modules.get('hermes_cli.plugins')
        # D-37 and Revisão F1–F5, R4: the manager of the home captured at register(), keyed as Hermes keys it.
        key = Path(home).expanduser().resolve() if home is not None else module._plugin_home_key()
        with module._plugin_managers_lock:
            manager = module._plugin_managers_by_home.get(key)
            tasks = manager._aux_tasks
            if not isinstance(tasks, dict) or any(not safe_name(name) or not isinstance(entry, dict) for name, entry in tasks.items()):
                return unavailable
            # Only identity and inheritance leave this reader, never provider or credential defaults.
            return {'ok': True, 'tasks': {name: {'inherit_from': entry['inherit_from']} if
                    isinstance(entry.get('inherit_from'), str) and safe_name(entry['inherit_from']) else {}
                    for name, entry in tasks.items()}}
    except Exception:
        return unavailable


# decisions/aux-plan.md, AUXP-02: pure path B; never read a session route or mutate main preferences.
def source_decision(pair, found, settings, now, previous, catalogs):
    from .mapping import catalog_gate
    from .policy import decide
    if not pair or 'conversation' not in settings['roles']:
        return {'state': 'source_map_not_approved', 'choice': None, 'tier': None,
                'reason': 'source_map_not_approved', 'states': {}, 'resets': []}
    blocked = {p: reason for p, cell in pair.items() if (reason := catalog_gate(p, cell['model'], catalogs))}
    if 'model_absent_from_catalog' in blocked.values():
        return {'state': 'catalog_model_absent', 'choice': None, 'tier': None,
                'reason': 'model_absent_from_catalog', 'states': {}, 'resets': []}
    result = decide('conversation', found, settings, now, previous=previous,
                    models={p: cell['model'] for p, cell in pair.items()}, blocked=blocked)
    return dict(result, state='decided' if result['choice'] else 'no_candidate')


# D-AUXP-6 revised: only normalized returned windows apply; no invented Sonnet window or per-task preference.
def task_decision(pair, source, found, settings, now, catalogs):
    from .mapping import catalog_gate
    from .policy import eligibility
    verdicts = {p: eligibility(found[p], settings, now, cell['model']) for p, cell in pair.items()}
    for verdict in verdicts.values():
        verdict.pop('_score', None)
    states = {p: verdict['state'] for p, verdict in verdicts.items()}
    result = {'choice': None, 'tier': None, 'state': 'no_candidate', 'reason': 'no_eligible_candidate',
              'model_state': states, 'eligibility': verdicts,
              'resets': sorted({r for v in verdicts.values() for r in v['resets']})}
    if source not in PROVIDERS:
        return result
    for provider in (source, next(p for p in PROVIDERS if p != source)):
        verdict = verdicts[provider]
        if verdict['state'] not in ('free', 'pressured') and not verdict['credits']:
            continue
        # D-AUXP-8/AUXP-03: catalog absence is not quota inelegibility and never licenses a cross-provider fallback.
        if provider == 'anthropic' and catalog_gate(provider, pair[provider]['model'], catalogs):
            return dict(result, state='catalog_model_absent', reason='model_absent_from_catalog')
        return dict(result, choice=provider, tier='subscription' if verdict['state'] in ('free', 'pressured') else 'credits',
                    state='decided' if provider == source else 'crossed_to_other_provider',
                    reason='source_followed' if provider == source else 'auxiliary_model_not_eligible')
    return dict(result, state='auxiliary_model_not_eligible', reason='auxiliary_model_not_eligible')


def task_name(group):
    if not isinstance(group, str) or not group.startswith(PREFIX) or not safe_name(group[len(PREFIX):]) or '.' in group[len(PREFIX):]:
        raise ValueError('Invalid auxiliary group')
    return group[len(PREFIX):]


def _shared_boundary(document, task):
    # AUXP-03/G7: aliases on containers or anchored leaves must not extend the mutation boundary.
    return aliased(document, [('auxiliary', task, field) for field in FIELDS])


def preconditions(document, group, route_projections=()):
    task = task_name(group)
    prefix = 'auxiliary.' + task
    if not isinstance(document, dict):
        return ['config']
    section = document.get('auxiliary')
    if not isinstance(section, dict):
        return ['auxiliary']
    node = section.get(task)
    if not isinstance(node, dict):
        return [prefix]
    try:
        if _shared_boundary(document, task):
            return ['yaml_alias_crosses_group']
    except (AttributeError, TypeError, RecursionError):
        return ['config']
    overlay = get(document, 'model.openai_runtime').get('value')
    if overlay is not None and not (isinstance(overlay, str) and not overlay.strip()):
        return ['model.openai_runtime']
    errors = [prefix + '.' + key for key in ('api_key', 'key_env', 'api_key_env')
              if key in node and node[key] not in (None, '')]
    if 'extra_body' in node and node['extra_body'] != {}:
        errors.append(prefix + '.extra_body')
    for projection in route_projections:
        validate_projection(group, projection)
    for field in FIELDS:
        if field not in node:
            continue
        value = node[field]
        if field in ('base_url', 'api_mode'):
            allowed = [p[field].get('value') for p in route_projections if p[field]['present']]
            valid = isinstance(value, str) and (value == '' or value in allowed)
        elif field == 'provider':
            valid = isinstance(value, str) and value in PROVIDERS
        elif field == 'model':
            valid = safe_model(value) is not None
        else:
            valid = isinstance(value, str) and value in EFFORTS
        if not valid:
            errors.append(prefix + '.' + field)
    return errors


def project(document, group, route_projections=()):
    if preconditions(document, group, route_projections):
        raise ValueError('Auxiliary preconditions failed')
    node = document['auxiliary'][task_name(group)]
    return {field: get(node, field) for field in FIELDS}


def validate_projection(group, projection):
    task_name(group)
    if not isinstance(projection, dict) or set(projection) != set(FIELDS):
        raise ValueError('Invalid closed auxiliary projection')
    for field, cell in projection.items():
        if not isinstance(cell, dict) or type(cell.get('present')) is not bool:
            raise ValueError('Invalid auxiliary presence marker')
        if set(cell) != ({'present', 'value'} if cell['present'] else {'present'}):
            raise ValueError('Invalid auxiliary projection cell')
        if not cell['present']:
            continue
        value = cell['value']
        valid = (isinstance(value, str) and value in PROVIDERS if field == 'provider' else
                 safe_model(value) is not None if field == 'model' else
                 isinstance(value, str) and value in EFFORTS if field == 'reasoning_effort' else value == '')
        if not valid:
            raise ValueError('Invalid auxiliary projected value')
    return projection


def target(group, selection, baseline=None):
    # AUXP-03: wire fields stay exactly as enrolled; approval Claude may omit effort (D-AUXP-7).
    validate_projection(group, baseline)
    result = deepcopy(baseline)
    result['provider'] = {'present': True, 'value': selection['provider']}
    result['model'] = {'present': True, 'value': selection['model']}
    result['reasoning_effort'] = ({'present': True, 'value': selection['effort']} if 'effort' in selection
                                  else {'present': False})
    return validate_projection(group, result)


def changes(document, group, projection):
    validate_projection(group, projection)
    prefix = 'auxiliary.' + task_name(group) + '.'
    return ({prefix + key: deepcopy(cell['value']) for key, cell in projection.items() if cell['present']},
            tuple(prefix + key for key, cell in projection.items() if not cell['present']))


def enrollment_errors(document, task, pair):
    # D-AUXP-2: map membership is an Auto-only admission gate, never a structural recovery condition.
    prefix = 'auxiliary.' + task
    node = get(document, prefix).get('value')
    if not isinstance(node, dict):
        return [prefix]
    provider = node.get('provider')
    if not isinstance(provider, str) or provider not in PROVIDERS:
        return [prefix + '.provider']
    if node.get('model') != pair.get(provider, {}).get('model'):
        return [prefix + '.model']
    return preconditions(document, PREFIX + task)
