# Implements decisions/hqr-20-amendment.md, section 16; decisions/s3-plan.md, "Escopo"; README.md, HQR-26.
"""Per-host source fingerprints; source-unavailable and any drift suspend every Auto write."""
import ast
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import sys
import types
import re

from . import compat_tables

DATA = Path(__file__).with_name('qualified_hosts.json')

# decisions/s3-plan.md, O1: cover native callees and dependencies, including the external model_map implementation.
FUNCTIONS = {
    'hermes_cli.config_backend': ('Changes', 'write_changes', 'write_config_keys', 'read_config_doc', '_route',
                                'get_config_backend', '_backend_for', '_ensure_bootstrap_env', '_bootstrap',
                                'FileBackend', 'FileBackend.write_path', 'FileBackend.read_path', 'FileBackend.write_changes'),
    'hermes_cli.config': ('get_config_path', 'load_config_readonly', '_split_key_path', '_greedy_literal_match'),
    # D18/R1: bind the default ladder, public route builders, final overlay and persisted selection shaping.
    'hermes_cli.model_switch': ('model_selection_config_updates', 'selection_route_changed', '_Switch.resolve_runtime',
        '_creds_for_switched_provider', '_creds_for_current_provider', '_resolve_switch_credentials',
        '_build_switch_result', 'model_derived_api_mode', 'switch_model'),
    'hermes_cli.route_identity': ('normalize_route_base_url', 'should_clear_context_pin'),
    'hermes_cli.runtime_provider': ('_explicit_codex', '_explicit_anthropic', 'resolve_runtime_provider',
        'resolve_requested_provider', '_ladder_rungs', '_get_model_config', 'load_config', '_runtime',
        '_resolve_requested_shortcuts', '_named_custom_rung', '_local_endpoint_bypass', '_resolve_explicit_runtime',
        '_resolve_from_pool', '_resolve_runtime_from_pool_entry', '_pool_entry_mode_and_url', '_pool_entry_base_url',
        '_effective_model', '_finalize_base_url', '_resolve_oauth_runtime', '_OAuthRuntimeSpec', '_anthropic_env_runtime',
        '_anthropic_cfg_base_url', '_anthropic_base_url_override_ok', '_config_base_url_for_provider', '_cfg_provider',
        '_same_registered_provider', '_maybe_apply_codex_app_server_runtime', '_detect_api_mode_for_url',
        'expand_direct_api_alias', '_resolve_named_custom_runtime', '_get_named_custom_provider',
        'resolve_codex_runtime_credentials', 'resolve_provider', '_resolves_to_custom'),
    'hermes_cli.runtime_provider_custom': ('expand_direct_api_alias', '_resolve_named_custom_runtime',
        '_get_named_custom_provider', '_select_named_custom_provider', '_shadowed_by_builtin',
        '_normalize_custom_provider_name', '_rp'),
    'hermes_cli.models': ('opencode_provider_family',),
    'hermes_cli.auth_codex': ('resolve_codex_runtime_credentials', '_codex_runtime_result', '_codex_base_url',
                            '_codex_pool_route_base_url'),
    'hermes_cli.auth': ('resolve_provider', '_plugin_aliases', '_registry_lookup'),
    'hermes_cli.providers': ('determine_api_mode', 'host_mandated_api_mode', 'is_actual_route', 'is_official_openai_host'),
    'utils': ('atomic_roundtrip_yaml_update', 'atomic_roundtrip_yaml_save', 'fast_safe_load', '_roundtrip_load',
              '_roundtrip_dump', '_atomic_write', '_preserve_file_mode', '_mode_for_write',
              'base_url_host_matches', 'base_url_hostname', 'base_url_path'),
    'hermes_yaml': ('safe_load', '_load', 'roundtrip_yaml'),
    'cron.scheduler': ('_resolve_job_reasoning_config',),
    'hermes_constants': ('resolve_reasoning_config', 'resolve_per_model_reasoning_effort', 'parse_reasoning_effort',
                         '_canonical_model_variants', 'get_hermes_home'),
    'tools.delegate_tool_config': ('_cfg', '_load_config', '_child_reasoning'),
    'tools.delegate_tool_routes': ('_active_provider', '_declared_parameters', '_route_one', '_clean_route', '_param_error'),
    'agent.delegation_provider': ('DelegationProvider.settings',),
    'agent.delegation_registry': ('configured_backend', 'get_active_provider', 'backend_status', '_usable'),
    'hermes_plugins.advanced_delegation.model_map': ('_text', '_entry_problem', '_is_codex', 'configured_options',
        'ModelMapDelegationProvider.task_parameters', 'ModelMapDelegationProvider.route_task'),
    'hermes_state_sessions': ('SessionSessionsMixin.get_session', 'SessionSessionsMixin.get_session_model_config_value'),
    'agent.models_dev': ('fetch_models_dev', '_load_disk_cache', '_validate_registry', '_get_cache_path', '_hermes_path',
                         '_quarantine_corrupt_cache', '_clear_etag', '_get_etag_path', '_quietly', '_disk_cache_age_seconds'),
    'hermes_cli.plugins_context': ('PluginContext.register_hook',),
    'hermes_cli.plugins_ledger': ('PluginRegistration.dispose',),
}
# decisions/hqr-38-spec.md, D-28/D-29; decisions/hqr-38-delivery.md: native code that reads and acts on `fallback_providers`.
# Entry normalization, root refresh in gateway/Desktop/CLI, cron inheritance, activation, primary restore and delegation.
SAFETY_NET = {
    'hermes_cli.fallback_config': ('_normalized_base_url', '_iter_fallback_entries', '_entry_identity',
                                   'get_fallback_chain', 'scoped_fallback_chain'),
    'gateway.run_config_loaders': ('GatewayConfigLoadersMixin._refresh_fallback_model',
                                   'GatewayConfigLoadersMixin._apply_fallback_chain_to_agent'),
    'tui_gateway.agent_callbacks': ('_sync_agent_fallback_with_config',),
    'hermes_cli.cli_chat_turn_mixin': ('CLIChatTurnMixin._sync_fallback_chain_with_config',),
    'cron.scheduler': ('_job_fallback_chain',),
    'agent.agent_init_fallback': ('_fallback_entries', '_init_fallback_chain'),
    'agent.chat_completion_helpers': ('try_activate_fallback',),
    'agent.agent_runtime_helpers': ('restore_primary_runtime',),
    'tools.delegate_tool_routes': ('_with_inherited_fallback', '_route_to_task_route'),
    'tools.delegate_tool_config': ('_resolve_child_fallback_chain', '_resolve_child_runtime'),
}
for _module, _names in SAFETY_NET.items():
    FUNCTIONS[_module] = FUNCTIONS.get(_module, ()) + tuple(n for n in _names if n not in FUNCTIONS.get(_module, ()))
del _module, _names
CONSTANTS = {'hermes_plugins.advanced_delegation.model_map': ('ROUTE_FIELDS', 'BACKEND', 'SETTINGS_PATH', 'PARAMETER', 'DAYBREAK_KEY'),
             'gateway.session_policy': ('FOLLOW_SECTIONS', 'FOLLOW_AGENT_KEYS'),
             'hermes_constants': ('VALID_REASONING_EFFORTS',),
             'agent.models_dev': ('PROVIDER_TO_MODELS_DEV',),
             'hermes_cli.auth_constants': ('DEFAULT_CODEX_BASE_URL',),
             'hermes_cli.auth': ('_PROVIDER_ALIASES',),
             'hermes_cli.runtime_provider': ('_ANTHROPIC_DEFAULT_BASE_URL', '_OAUTH_RUNTIME_PROVIDERS', '_POOL_ENTRY_SIMPLE_MODES',
                                             '_HOST_MANDATED_API_MODES'),
             'hermes_cli.runtime_provider_custom': ('_DIRECT_API_BASE_URLS',),
             'hermes_cli.model_switch': ('_PROVIDER_API_MODE_OVERRIDES',),
             'hermes_cli.providers': ('TRANSPORT_TO_API_MODE', '_RESPONSES_NATIVE_HOSTS')}


def fingerprint(function):
    return hashlib.sha256(inspect.getsource(function).encode('utf-8')).hexdigest()


def verify(expected, functions, constants):
    reasons = []
    for name, digest in expected['functions'].items():
        try:
            if fingerprint(functions[name]) != digest:
                reasons.append(name)
        except (KeyError, OSError, TypeError, IndentationError):
            reasons.append(name)
    for name, value in expected['constants'].items():
        actual = constants.get(name)
        if isinstance(actual, (tuple, set, frozenset)):
            actual = sorted(actual) if isinstance(actual, (set, frozenset)) else list(actual)
        if actual != value:
            reasons.append(name)
    return {'ok': not reasons, 'reasons': sorted(reasons)}


# decisions/s3-delivery.md, SEC-S3-05: AST inspection must never execute defaults, annotations or decorators.
def source_object(path, qualified, *, root=None, seen=frozenset()):
    """Inspect definitions and reexports without executing a native module or expression."""
    path = Path(path).resolve(strict=True)
    root = Path(root).resolve(strict=True) if root is not None else path.parent
    identity = (path, qualified)
    if not path.is_relative_to(root) or identity in seen:
        raise ValueError('Source alias escapes root or cycles')
    source = path.read_text(encoding='utf-8')
    scope = ast.parse(source, filename=str(path))
    parts = qualified.split('.')
    for index, part in enumerate(parts):
        definitions = [n for n in scope.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == part]
        if not definitions and index == 0:
            imports = [(n, alias) for n in scope.body if isinstance(n, ast.ImportFrom) for alias in n.names
                       if (alias.asname or alias.name) == part]
            if len(imports) != 1:
                raise ValueError('Source definition unavailable')
            node, alias = imports[0]
            base = (path.parent if node.level == 1 else path.parents[node.level - 1]) if node.level else root
            target = base.joinpath(*(node.module or '').split('.')).with_suffix('.py')
            return source_object(target, '.'.join([alias.name, *parts[1:]]), root=root, seen=seen | {identity})
        if len(definitions) != 1:
            raise ValueError('Ambiguous source definition')
        scope = definitions[0]
    first = min([scope.lineno] + [d.lineno for d in scope.decorator_list])
    return ''.join(inspect.getblock(source.splitlines(keepends=True)[first - 1:]))


def source_constant(path, name):
    if name in compat_tables.TABLES:
        return compat_tables.binding(path, name)
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    assignments = {}
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        for target in targets:
            if isinstance(target, ast.Name):
                assignments[target.id] = node.value
    def literal(value, seen):
        if isinstance(value, ast.Name):
            if value.id in seen or value.id not in assignments:
                raise ValueError('Constant dependency unavailable')
            return literal(assignments[value.id], seen | {value.id})
        if isinstance(value, ast.JoinedStr):
            pieces = []
            for part in value.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    pieces.append(part.value)
                elif isinstance(part, ast.FormattedValue) and part.conversion == -1 and part.format_spec is None:
                    resolved = literal(part.value, seen)
                    if not isinstance(resolved, (str, int, bool)):
                        raise ValueError('Constant interpolation unavailable')
                    pieces.append(str(resolved))
                else:
                    raise ValueError('Constant interpolation unavailable')
            return ''.join(pieces)
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in ('set', 'frozenset', 'tuple'):
            if len(value.args) != 1 or value.keywords:
                raise ValueError('Constant container unavailable')
            value = value.args[0]
        return ast.literal_eval(value)
    if name not in assignments:
        raise ValueError('Constant source unavailable')
    result = literal(assignments[name], {name})
    return sorted(result) if isinstance(result, (set, frozenset)) else list(result) if isinstance(result, tuple) else result


def collect_symbols(root, specs=FUNCTIONS, constant_specs=CONSTANTS, *, plugin_root=None):
    functions, constants = {}, {}
    for module_name, names in specs.items():
        prefix = 'hermes_plugins.advanced_delegation.'
        if module_name.startswith(prefix):
            base = Path(plugin_root) if plugin_root is not None else Path(root).parent / 'plugins' / 'advanced-delegation'
            path = base.joinpath(*module_name.removeprefix(prefix).split('.')).with_suffix('.py')
        else:
            path = Path(root).joinpath(*module_name.split('.')).with_suffix('.py')
        for name in names:
            key = module_name + '.' + name
            loaded = sys.modules.get(module_name)
            if module_name.startswith(prefix):
                registry = getattr(sys.modules.get('agent.delegation_registry'), '_registry', None)
                provider = registry.get_provider('model_map') if registry is not None else None
                if provider is not None:
                    # The active home may own a suffixed namespace; never attest a different home's bare module.
                    loaded = sys.modules.get(type(provider).__module__, types.SimpleNamespace())
            value = loaded
            try:
                for part in name.split('.'):
                    value = getattr(value, part)
            except AttributeError:
                value = None
            # decisions/s3-plan.md, R4/O1: an active override cannot borrow pristine disk bytes when inspection fails.
            if loaded is not None:
                try:
                    functions[key] = fingerprint(value) if value is not None else None
                except (TypeError, OSError):
                    functions[key] = None
            else:
                try:
                    functions[key] = hashlib.sha256(source_object(path, name, root=base if module_name.startswith(prefix) else root).encode()).hexdigest()
                except (OSError, ValueError, StopIteration, SyntaxError, TypeError):
                    functions[key] = None
    for module_name, names in constant_specs.items():
        for name in names:
            key = module_name + '.' + name
            try:
                loaded = sys.modules.get(module_name)
                prefix = 'hermes_plugins.advanced_delegation.'
                if module_name.startswith(prefix):
                    base = Path(plugin_root) if plugin_root is not None else Path(root).parent / 'plugins' / 'advanced-delegation'
                    path = base.joinpath(*module_name.removeprefix(prefix).split('.')).with_suffix('.py')
                    registry = getattr(sys.modules.get('agent.delegation_registry'), '_registry', None)
                    provider = registry.get_provider('model_map') if registry is not None else None
                    if provider is not None:
                        loaded = sys.modules.get(type(provider).__module__, types.SimpleNamespace())
                else:
                    path = Path(root).joinpath(*module_name.split('.')).with_suffix('.py')
                value = (compat_tables.binding(path, name, loaded) if name in compat_tables.TABLES else
                         getattr(loaded, name) if loaded is not None else source_constant(path, name))
                constants[key] = sorted(value) if isinstance(value, (set, frozenset)) else list(value) if isinstance(value, tuple) else value
            except (OSError, ValueError, SyntaxError, TypeError, AttributeError, KeyError, StopIteration):
                constants[key] = None
    return {'functions': functions, 'constants': constants}


def native_revision(root):
    git = Path(root) / '.git'
    if git.is_file():
        text = git.read_text(encoding='utf-8').strip()
        if not text.startswith('gitdir: '):
            raise ValueError('Git metadata unavailable')
        git = (git.parent / text.removeprefix('gitdir: ')).resolve(strict=True)
    head = (git / 'HEAD').read_text(encoding='utf-8').strip()
    if head.startswith('ref: '):
        ref = head.removeprefix('ref: ')
        if not ref.startswith('refs/') or '..' in Path(ref).parts:
            raise ValueError('Git reference unavailable')
        common = git
        if (git / 'commondir').is_file():
            common = (git / (git / 'commondir').read_text(encoding='utf-8').strip()).resolve(strict=True)
        try:
            head = (common / ref).read_text(encoding='utf-8').strip()
        except FileNotFoundError:
            lines = (common / 'packed-refs').read_text(encoding='utf-8').splitlines()
            head = next(line.split()[0] for line in lines if len(line.split()) == 2 and line.split()[1] == ref)
    if not re.fullmatch('[0-9a-f]{40}', head):
        raise ValueError('Git revision unavailable')
    return head


def _source_compatibility():
    if os.environ.get('HERMES_CONFIG_BACKEND', '').strip().lower() not in ('', 'file'):
        return {'ok': False, 'reasons': ['config_backend_not_file']}
    try:
        # config_backend's module body defines types only; no config loader, credential reader or launcher is called.
        module = importlib.import_module('hermes_cli.config_backend')
        root = Path(module.__file__).resolve().parents[1]
        hosts = json.loads(DATA.read_text(encoding='utf-8'))['hosts']
        # HQR-26; decisions/s3-plan.md, fingerprint qualification: Git adds a constraint, never replaces the full set.
        try:
            revision = native_revision(root)
        except (OSError, ValueError, StopIteration):
            revision = None
        candidates = [host for host in hosts if
                      (host['revision'] == revision if revision is not None else host.get('allow_revisionless_match') is True)]
        # decisions/hqr-38-delivery.md: an entry measured before a required symbol was added fails closed until requalified.
        pending = [host for host in candidates if host.get('requalification_required')]
        candidates = [host for host in candidates if not host.get('requalification_required')]
        if pending and not candidates:
            return {'ok': False, 'reasons': ['host_requalification_required'], 'host': pending[0]['label'],
                    'revision': revision, 'qualified_revision': pending[0]['revision']}
        if not candidates:
            return {'ok': False, 'reasons': ['host_not_qualified' if revision is not None else 'native_source_unavailable']}
        from hermes_constants import get_hermes_home
        actual = collect_symbols(root, plugin_root=get_hermes_home() / 'plugins' / 'advanced-delegation')
        required = {kind: {module + '.' + name for module, names in specs.items() for name in names}
                    for kind, specs in (('functions', FUNCTIONS), ('constants', CONSTANTS))}
        checks = []
        # README.md, HQR-26: one entry must bind every required function and constant, with no partial or extra set.
        for host in candidates:
            reasons = [key for kind in ('functions', 'constants') for key in required[kind] | set(host[kind]) | set(actual[kind])
                       if key not in required[kind] or host[kind].get(key) is None or actual[kind].get(key) != host[kind].get(key)]
            checks.append((reasons, host))
        reasons, host = min(checks, key=lambda pair: len(pair[0]))
        from .routes import mirror_matches
        if not reasons and not mirror_matches(host['constants']):
            reasons.append('native_default_route_mirror')
        result = {'ok': not reasons, 'reasons': sorted(reasons), 'host': host['label'], 'revision': revision,
                  'qualified_revision': host['revision']}
        if revision is None and not reasons:
            result['revision_note'] = 'revisão do Hermes não identificada; impressões conferem'
        return result
    except Exception:
        return {'ok': False, 'reasons': ['native_source_unavailable']}



# decisions/s3-delivery.md, "Continuação": inspect registration only; dependency absence must never trigger discovery or auth.
def native_delegation_status(config=None):
    """Read the current registration only; never trigger discovery, auth or a mutating config loader."""
    unavailable = {'ok': False, 'reason': 'advanced_delegation_unavailable', 'required_version': '1.1.0'}
    try:
        if config is None:
            from hermes_cli.config import get_config_path
            from hermes_cli.config_backend import read_config_doc
            config = read_config_doc(get_config_path())
        plugins = config.get('plugins', {})
        if ('advanced-delegation' not in plugins.get('enabled', []) or
                'advanced-delegation' in plugins.get('disabled', []) or config.get('delegation', {}).get('backend') != 'model_map'):
            return unavailable
        module = sys.modules.get('agent.delegation_registry')
        registry = getattr(module, '_registry', None)
        provider = registry.get_provider('model_map') if registry is not None else None
        if provider is None or not provider.is_available():
            return unavailable
        return {'ok': True, 'backend': 'model_map', 'required_version': '1.1.0'}
    except Exception:
        return unavailable


def native_compatibility():
    return dict(_source_compatibility(), subagents=native_delegation_status())
