# Implements decisions/hqr-20-amendment.md, D18: credential-free native default route mirror.
"""Closed public defaults; never resolve a provider or inspect authentication/configuration."""

# D18/R1 binds the mirror to the complete default ladder, OAuth/pool tables, URL builders,
# final runtime overlay and model-switch shaping in compat.py, not only explicit-credential builders.
# A changed native source must be qualified together with this mirror before any Auto write.
DEFAULT_ROUTES = {
    'openai-codex': {'base_url': 'https://chatgpt.com/backend-api/codex', 'api_mode': 'codex_responses'},
    'anthropic': {'base_url': 'https://api.anthropic.com', 'api_mode': 'anthropic_messages'},
}


def mirror_matches(constants):
    """D18: qualifying changed native constants alone cannot silently bless an obsolete mirror."""
    # D18/R1: even a requalified alias table cannot redirect a managed provider behind this mirror.
    aliases = constants.get('hermes_cli.auth._PROVIDER_ALIASES', {})
    if not isinstance(aliases, dict) or any(aliases.get(provider, provider) != provider for provider in DEFAULT_ROUTES):
        return False
    modes = constants.get('hermes_cli.providers.TRANSPORT_TO_API_MODE') or {}
    expected = {
        'openai-codex': {'base_url': constants.get('hermes_cli.auth_constants.DEFAULT_CODEX_BASE_URL'),
                         'api_mode': modes.get('codex_responses')},
        'anthropic': {'base_url': constants.get('hermes_cli.runtime_provider._ANTHROPIC_DEFAULT_BASE_URL'),
                      'api_mode': modes.get('anthropic_messages')},
    }
    runtime = 'hermes_cli.runtime_provider.'
    for name in ('_OAUTH_RUNTIME_PROVIDERS', '_POOL_ENTRY_SIMPLE_MODES'):
        if runtime + name not in constants:
            continue
        cells = constants[runtime + name]['routes']
        codex = cells.get('openai-codex', {})
        if codex.get('api_mode') != DEFAULT_ROUTES['openai-codex']['api_mode']:
            return False
        if name == '_POOL_ENTRY_SIMPLE_MODES' and codex.get('base_url') != DEFAULT_ROUTES['openai-codex']['base_url']:
            return False
        if 'anthropic' in cells:
            return False
    overrides = constants.get('hermes_cli.model_switch._PROVIDER_API_MODE_OVERRIDES')
    if overrides is not None and overrides['routes']:
        return False
    return expected == DEFAULT_ROUTES


def defaults(provider):
    return dict(DEFAULT_ROUTES.get(provider, {})) if isinstance(provider, str) else {}
