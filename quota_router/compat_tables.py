# Implements decisions/hqr-20-amendment.md, D18/R1: inert binding of default-route dispatch tables.
"""Inspect a closed source grammar and live public route cells without calling native code."""
import ast
import hashlib
from pathlib import Path
import types

TABLES = ('_OAUTH_RUNTIME_PROVIDERS', '_POOL_ENTRY_SIMPLE_MODES', '_PROVIDER_API_MODE_OVERRIDES')
PROVIDERS = ('openai-codex', 'anthropic')


def lambda_shape(node):
    if not isinstance(node, ast.Lambda):
        raise ValueError('OAuth resolver is not an inspectable lambda')
    # AST dump defaults differ between supported Python versions; omit empty optional fields explicitly.
    def shape(value):
        if isinstance(value, ast.AST):
            return [type(value).__name__, {key: shape(item) for key, item in ast.iter_fields(value) if item is not None and item != []}]
        return [shape(item) for item in value] if isinstance(value, list) else value
    return shape(node)


def loaded_lambda(value):
    if type(value) is not types.FunctionType or value.__code__.co_name != '<lambda>':
        raise ValueError('OAuth resolver source unavailable')
    # D18/R1/R3: an inline dictionary entry is not a standalone Python module.
    # Parse the complete source, tied to the active function's filename and first line; never execute it.
    code = value.__code__
    tree = ast.parse(Path(code.co_filename).read_text(encoding='utf-8'))
    lambdas = [node for node in ast.walk(tree) if isinstance(node, ast.Lambda) and node.lineno == code.co_firstlineno]
    if len(lambdas) != 1:
        raise ValueError('Ambiguous OAuth resolver source')
    return lambda_shape(lambdas[0])


def table_items(node):
    """Only dictionary literals and literal dict.fromkeys expansion; never eval/compile/import."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) \
            and node.func.value.id == 'dict' and node.func.attr == 'fromkeys' and len(node.args) == 2 and not node.keywords:
        keys = ast.literal_eval(node.args[0])
        if not isinstance(keys, (tuple, list)) or not all(type(key) is str for key in keys):
            raise ValueError('Dispatch keys unavailable')
        return dict.fromkeys(keys, node.args[1])
    if not isinstance(node, ast.Dict):
        raise ValueError('Dispatch table source unavailable')
    result = {}
    for key, value in zip(node.keys, node.values):
        if key is None:
            result.update(table_items(value))
        else:
            key = ast.literal_eval(key)
            if type(key) is not str or key in result:
                raise ValueError('Ambiguous dispatch key')
            result[key] = value
    return result


def source_routes(path, name, node):
    items = table_items(node)
    routes = {}
    for provider in PROVIDERS:
        if provider not in items:
            continue
        value = items[provider]
        if name == '_PROVIDER_API_MODE_OVERRIDES':
            routes[provider] = {'present': True}
        elif name == '_POOL_ENTRY_SIMPLE_MODES':
            if not isinstance(value, ast.Tuple) or len(value.elts) != 2:
                raise ValueError('Pool route source unavailable')
            mode, url = value.elts
            if isinstance(url, ast.Name) and url.id == 'DEFAULT_CODEX_BASE_URL':
                constants = Path(path).with_name('auth_constants.py')
                tree = ast.parse(constants.read_text(encoding='utf-8'))
                url = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == url.id for t in n.targets))
            routes[provider] = {'api_mode': ast.literal_eval(mode), 'base_url': ast.literal_eval(url)}
        else:
            if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id != '_OAuthRuntimeSpec':
                raise ValueError('OAuth spec source unavailable')
            fields = ('resolve', 'api_mode', 'default_source', 'expiry_key', 'failure_msg', 'default_base_url')
            if len(value.args) > len(fields) or any(k.arg not in fields for k in value.keywords):
                raise ValueError('OAuth spec fields unavailable')
            args: dict[str, ast.AST] = dict(zip(fields, value.args))
            for key in value.keywords:
                if key.arg in args:
                    raise ValueError('Duplicate OAuth field')
                args[key.arg] = key.value
            routes[provider] = {'api_mode': ast.literal_eval(args['api_mode']),
                                'default_base_url': ast.literal_eval(args.get('default_base_url', ast.Constant(value=''))),
                                'resolve': lambda_shape(args['resolve'])}
    return routes


def loaded_routes(name, value):
    if type(value) is not dict:
        raise ValueError('Loaded dispatch table unavailable')
    routes = {}
    for provider in PROVIDERS:
        if provider not in value:
            continue
        entry = value[provider]
        if name == '_PROVIDER_API_MODE_OVERRIDES':
            routes[provider] = {'present': True}
        elif name == '_POOL_ENTRY_SIMPLE_MODES':
            if type(entry) is not tuple or len(entry) != 2 or not all(type(cell) is str for cell in entry):
                raise ValueError('Loaded pool route unavailable')
            routes[provider] = {'api_mode': entry[0], 'base_url': entry[1]}
        else:
            # vars reads stored fields only; do not evaluate native properties or call a spec/credential resolver.
            fields = vars(entry)
            if any(type(fields.get(key)) is not str for key in ('api_mode', 'default_base_url')):
                raise ValueError('Loaded OAuth fields unavailable')
            routes[provider] = {'api_mode': fields['api_mode'], 'default_base_url': fields['default_base_url'],
                                'resolve': loaded_lambda(fields['resolve'])}
    return routes


def binding(path, name, loaded=None):
    source = Path(path).read_text(encoding='utf-8')
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
               and any(isinstance(target, ast.Name) and target.id == name
                       for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))]
    if len(matches) != 1:
        raise ValueError('Ambiguous dispatch assignment')
    node = matches[0]
    routes = source_routes(path, name, node.value)
    if loaded is not None and loaded_routes(name, vars(loaded)[name]) != routes:
        raise ValueError('Loaded dispatch route differs from source')
    block = ''.join(source.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])
    return {'source_sha256': hashlib.sha256(block.encode('utf-8')).hexdigest(), 'routes': routes}
