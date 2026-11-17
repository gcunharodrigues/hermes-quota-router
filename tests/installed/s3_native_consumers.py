"""In-target native resolution probes; stdlib imports until explicitly exercised.

These probes use only absent credentials or a credential-free loopback metadata stub, and stop before agent construction and inference.
A missing native seam is a failing scenario, never a synthetic success.
HQR-32 guard and worker corrections are recorded in decisions/s3-delivery.md.
"""
import ast
from contextlib import contextmanager
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

REQUIRED = ('C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C10', 'C12', 'E2', 'AC-22')


class ProbeFailure(RuntimeError):
    pass


class IncompleteProof(ProbeFailure):
    def __init__(self, reason, observed):
        super().__init__(reason)
        self.observed = observed


def decode_model_config(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError as exc:
            raise ProbeFailure('invalid native model_config JSON') from exc
    if not isinstance(value, dict):
        raise ProbeFailure('native model_config must be an object')
    return value


def dependency_inventory(root, expected):
    root = Path(root)
    ensure(root.is_dir() and not root.is_symlink(), 'dependency root is not a plain directory')
    actual, special = {}, []
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            special.append(str(relative))
        elif path.is_file():
            actual[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    ensure(isinstance(expected, dict) and bool(expected), 'dependency byte manifest missing')
    ensure(all(isinstance(name, str) and not Path(name).is_absolute() and '..' not in Path(name).parts and
               isinstance(digest, str) and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)
               for name, digest in expected.items()), 'invalid dependency byte manifest')
    return {'bytes_match': actual == expected, 'special': sorted(special), 'files': len(actual)}


def require_complete(report):
    if report.get('audit_denied'):
        raise ProbeFailure('forbidden native probe operations were attempted: ' + ', '.join(report['audit_denied']))
    scenarios = report.get('scenarios', {})
    missing = [name + ': ' + str(scenarios.get(name, {}).get('reason', 'native proof missing'))
               for name in REQUIRED if scenarios.get(name, {}).get('pass') is not True]
    if missing:
        raise ProbeFailure('; '.join(missing))


def stop_at_call(invoke, boundary):
    """Execute native callers, then unwind BEFORE a boundary's body, without supplying a fake return."""
    class BoundaryReached(BaseException):
        pass
    found = {}
    previous = sys.gettrace()
    def trace(frame, event, _arg):
        if event == 'call' and frame.f_code is boundary.__code__:
            import inspect
            parameters = inspect.signature(boundary).parameters
            found.update(callee={k: v for k, v in frame.f_locals.items() if k in parameters}, caller=dict(frame.f_back.f_locals))
            raise BoundaryReached()
        return trace
    try:
        sys.settrace(trace)
        try:
            invoke()
        except BoundaryReached:
            return found
        raise ProbeFailure('native boundary not reached')
    finally:
        sys.settrace(previous)


def source_verdict(*, started_stable, model_config_immutable, capture_order):
    reasons = [label for value, label in ((started_stable, 'started_at_not_immutable'),
               (model_config_immutable, 'model_config_mutable'), (capture_order, 'capture_order_unproven')) if value is not True]
    return {'qualified': not reasons, 'reasons': reasons}


class UnsafeProbe(BaseException):
    """Not swallowed by native fail-open readers or scenario exception handling."""


class ProbeGuard:
    metadata_paths = frozenset(('/models-dev.json', '/v1/models', '/models', '/api/tags', '/api/version'))

    def __init__(self, home, *, missing_credentials=False):
        self.home = Path(home).resolve(strict=True)
        self.missing_credentials = missing_credentials
        self.missing_roots = {self.home}
        self.absent_credentials = []
        self.denied = []
        self.workers = set()
        self.readonly_commands = set()
        from threading import local
        self._scanner_state = local()
        self.metadata_address = None
        self.listener_socket = None

    @contextmanager
    def scanner_git(self, root):
        # SEC-S3-06: the native bytecode scanner queries only this target tree's index.
        root = Path(root)
        ensure(root.is_absolute() and root.is_dir() and not root.is_symlink() and root.resolve().is_relative_to(self.home),
               'scanner root outside admitted home')
        command = ('git', '-c', 'core.fsmonitor=false', '-C', str(root), 'ls-files', '-z', '--', '*.pyc', '*.pyo')
        # HQR-32 SEC-01: qualify Git independently of PATH, then bind the entire admitted environment.
        import shutil
        executable = shutil.which('git', path='/usr/bin:/bin')
        if executable is None:
            raise ProbeFailure('qualified scanner Git missing')
        git = str(Path(executable).resolve(strict=True))
        environment = dict(os.environ)
        selected = shutil.which('git', path=environment.get('PATH', os.defpath))
        ensure(selected is not None and str(Path(selected).resolve(strict=True)) == git, 'scanner PATH selects unqualified Git')
        # HQR-32 SEC-02: replacement revokes the older call; exits never restore saved capabilities.
        previous = getattr(self._scanner_state, 'admission', None)
        if previous is not None:
            previous['active'] = False
        admitted = {'command': command, 'git': git, 'env': environment, 'active': True, 'used': False}
        self._scanner_state.admission = admitted
        try:
            yield
        finally:
            admitted['active'] = False
            current = getattr(self._scanner_state, 'admission', None)
            if current is not None:
                current['active'] = False
            self._scanner_state.admission = None

    @property
    def scanner_admission(self):
        admitted = getattr(self._scanner_state, 'admission', None)
        return admitted if admitted is not None and admitted['active'] and not admitted['used'] else None

    @property
    def scanner_devnull(self):
        return self.scanner_admission is not None

    def scanner_process(self, args):
        import shutil
        admitted = self.scanner_admission
        if admitted is None or tuple(args[1]) != admitted['command'] or args[2] is not None:
            return False
        environment = dict(os.environ) if args[3] is None else args[3]
        if environment != admitted['env'] or args[0] not in ('git', admitted['git']):
            return False
        # The native scanner spells argv[0] as git; that spelling must still resolve to the qualified path.
        selected = shutil.which('git', path=admitted['env'].get('PATH', os.defpath))
        if selected is None or str(Path(selected).resolve(strict=True)) != admitted['git']:
            return False
        admitted['used'] = True
        return True

    def wrap_open(self, original):
        # CPython's open audit event omits dir_fd; bind that missing fact before the real syscall.
        from contextvars import ContextVar
        self.open_target = ContextVar('hqr_guard_open_target', default=None)
        def wrapped(path, flags, mode=0o777, *, dir_fd=None):
            target = self.mutation_path(path, dir_fd)
            token = self.open_target.set(target)
            try:
                self.audit('open', (str(target), None, flags))
                return original(path, flags, mode, dir_fd=dir_fd)
            finally:
                self.open_target.reset(token)
        return wrapped

    def mutation_path(self, value, directory=-1):
        if isinstance(value, int):
            return Path(os.readlink('/proc/self/fd/' + str(value))).resolve()
        path = Path(os.fsdecode(value))
        if not path.is_absolute() and directory not in (-1, None):
            path = Path(os.readlink('/proc/self/fd/' + str(directory))) / path
        return path.resolve()

    def audit(self, event, args):
        if event == 'sqlite3.connect' and args[0] == ':memory:':
            return
        bad = event in ('socket.connect', 'socket.getaddrinfo', 'urllib.Request', 'http.client.connect',
                        'os.system', 'os.exec', 'os.posix_spawn')
        if event in ('socket.connect', 'socket.getaddrinfo') and self.metadata_address is not None:
            address = args[1] if event == 'socket.connect' else args[:2]
            bad = tuple(address) != self.metadata_address
        if event == 'socket.bind':
            if args[1] == ('::1', 0):
                # urllib3's optional IPv6 capability check: refuse before bind, let it use IPv4.
                raise OSError('IPv6 capability probe blocked; only the exact IPv4 metadata stub is admitted')
            bad = args[0] is not self.listener_socket or args[1] != ('127.0.0.1', 0)
        if event in ('urllib.Request', 'http.client.connect') and self.metadata_address is not None:
            if event == 'urllib.Request':
                from urllib.parse import urlsplit
                url = urlsplit(args[0])
                bad = (url.scheme != 'http' or (url.hostname, url.port) != self.metadata_address or
                       args[3] != 'GET' or url.path not in self.metadata_paths or bool(url.query))
            else:
                bad = tuple(args[1:3]) != self.metadata_address
        if event == 'http.client.send' and self.metadata_address is not None:
            line = args[1].split(b'\r\n', 1)[0].split(b' ')
            bad = len(line) != 3 or line[0] != b'GET' or line[1].decode('ascii') not in self.metadata_paths
        if event == 'subprocess.Popen':
            bad = (tuple(args[1]) not in self.workers and not self.scanner_process(args) and
                   (tuple(args[1]), str(args[2])) not in self.readonly_commands)
        one_path = {'os.remove': 1, 'os.rmdir': 1, 'os.mkdir': 2, 'os.chmod': 2, 'os.chown': 3,
                    'os.utime': 3, 'os.truncate': None}
        if event in one_path:
            index = one_path[event]
            directory = args[index] if index is not None and len(args) > index else -1
            bad = not self.mutation_path(args[0], directory).is_relative_to(self.home)
        if event in ('os.rename', 'os.link'):
            bad = any(not self.mutation_path(args[i], args[i + 2] if len(args) > i + 2 else -1).is_relative_to(self.home)
                      for i in (0, 1))
        if event == 'os.symlink':
            bad = True  # Native config/session probes have no reason to create links.
        if event in ('open', 'sqlite3.connect') and isinstance(args[0], (str, bytes, os.PathLike)):
            raw_path = os.fsdecode(args[0])
            if event == 'sqlite3.connect' and raw_path.startswith('file:'):
                from urllib.parse import unquote, urlsplit
                uri = urlsplit(raw_path)
                if uri.netloc:
                    self.denied.append(event)
                    raise UnsafeProbe('native probe refused remote SQLite URI')
                raw_path = unquote(uri.path)
            bound = getattr(self, 'open_target', None)
            path = bound.get() if event == 'open' and bound is not None and bound.get() is not None else Path(raw_path).resolve()
            own = path.is_relative_to(self.home)
            bad = path.name in ('auth.json', '.env', '.netrc', '.git-credentials')
            absent_scope = any(path.is_relative_to(root) for root in self.missing_roots)
            if bad and absent_scope and self.missing_credentials and not path.exists() and event == 'open':
                # Never open credentials, including absent files: preserve only their verified missing-file condition.
                self.absent_credentials.append(path.name)
                raise FileNotFoundError(2, 'absent credential file blocked before open', str(path))
            bad |= not own and (path.name == 'config.yaml' or path.name.startswith('state.db'))
            if event == 'sqlite3.connect':
                bad |= not own
            else:
                mode, flags = args[1:3]
                writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                    isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)))
                # SEC-S3-06: DEVNULL is a verified sink, only during the exact scanner query.
                null_sink = (self.scanner_devnull and path == Path('/dev/null') and isinstance(flags, int) and
                             flags & ~os.O_CLOEXEC == os.O_RDWR and stat.S_ISCHR(path.stat().st_mode) and
                             path.stat().st_rdev == os.makedev(1, 3))
                bad |= writing and not own and not null_sink
        if bad:
            self.denied.append(event)
            raise UnsafeProbe('native probe refused forbidden operation: ' + event)


def ensure(condition, reason):
    if not condition:
        raise ProbeFailure(reason)


def check_route(actual, expected):
    ensure(all(actual.get(k) == expected.get(k) and actual.get(k) is not None for k in ('provider', 'model', 'effort')),
           'native provider/model/effort differ: ' + json.dumps({'actual': actual, 'expected': expected}, sort_keys=True))
    return actual


def case(function) -> dict[str, Any]:
    try:
        return {'pass': True, 'observed': function()}
    except (ProbeFailure, UnsafeProbe) as exc:
        result = {'pass': False, 'reason': str(exc)}
        if isinstance(exc, IncompleteProof):
            result['observed'] = exc.observed
        return result
    except Exception as exc:
        # No exception payload: a native loader may include private fields in its message.
        return {'pass': False, 'reason': 'native probe raised ' + type(exc).__name__}


class MetadataStub:
    """Only metadata, on this process's exact loopback socket; POST never has a handler."""
    def __init__(self, guard):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from threading import Thread
        self.requests = []
        requests = self.requests
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                requests.append({'method': 'GET', 'path': self.path})
                if self.path == '/models-dev.json':
                    data = {'hqr-proof': {'id': 'hqr-proof', 'name': 'Synthetic metadata only', 'env': [], 'models': {}}}
                elif self.path in ('/v1/models', '/models'):
                    data = {'object': 'list', 'data': [{'id': 'hqr-explicit', 'object': 'model', 'owned_by': 'synthetic'}]}
                elif self.path in ('/api/tags', '/api/version'):
                    self.send_error(404)
                    return
                else:
                    self.send_error(403)
                    return
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = HTTPServer(('127.0.0.1', 0), Handler, bind_and_activate=False)
        guard.listener_socket = self.server.socket
        self.server.server_bind()
        self.server.server_activate()
        guard.metadata_address = self.server.server_address
        self.guard = guard
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.guard.metadata_address = None
        self.guard.listener_socket = None


class NativeHost:
    def __init__(self):
        backend = importlib.import_module('hermes_cli.config_backend')
        filename = backend.__file__
        if not isinstance(filename, str):
            raise ProbeFailure('native config backend source unavailable')
        self.root = Path(filename).resolve().parents[1]
        self.sources = {}
        self.plugin_root = Path(os.environ['HERMES_HOME']) / 'plugins' / 'advanced-delegation'

    def function(self, module, name) -> Any:
        value: Any = importlib.import_module(module)
        for part in name.split('.'):
            value = getattr(value, part, None)
        ensure(callable(value), 'native function unavailable: ' + module + '.' + name)
        original = inspect.unwrap(value)
        filename = inspect.getsourcefile(original)
        if not isinstance(filename, str):
            raise ProbeFailure('native source unavailable: ' + module + '.' + name)
        path = Path(filename).resolve()
        ensure(path.is_relative_to(self.root), 'native function outside host source: ' + module + '.' + name)
        source = inspect.getsource(original)
        self.sources[module + '.' + name] = {'file': str(path.relative_to(self.root)),
            'line': inspect.getsourcelines(original)[1], 'sha256': hashlib.sha256(source.encode()).hexdigest()}
        return value

    def plugin_function(self, value):
        original = inspect.unwrap(value)
        filename = inspect.getsourcefile(original)
        ensure(isinstance(filename, str), 'native plugin source unavailable')
        path = Path(filename).resolve()
        ensure(path.is_relative_to(self.plugin_root.resolve()), 'native plugin function outside copied dependency')
        self.sources[original.__module__ + '.' + original.__qualname__] = {
            'file': 'plugins/advanced-delegation/' + str(path.relative_to(self.plugin_root.resolve())),
            'line': inspect.getsourcelines(original)[1], 'sha256': hashlib.sha256(inspect.getsource(original).encode()).hexdigest()}
        return value

    def load_delegation(self):
        manifest = self.function('hermes_yaml', 'safe_load')((self.plugin_root / 'plugin.yaml').read_text())
        ensure(manifest.get('version') == '1.1.0', 'advanced-delegation version differs from qualified pin')
        self.function('hermes_cli.plugins', 'discover_plugins')()
        active = self.function('agent.delegation_registry', 'get_active_provider')({'backend': 'model_map'})
        self.plugin_function(type(active).task_parameters)
        self.plugin_function(type(active).route_task)
        return {'version': manifest['version'], 'backend': active.name, 'loaded': True}

    def route(self, config, model=None):
        model = model or self.function('gateway.run', '_resolve_gateway_model')(config)
        reasoning = self.function('hermes_constants', 'resolve_reasoning_config')(config, model)
        ensure(isinstance(reasoning, dict), 'native effort was not resolved')
        scope = self.function('hermes_cli.runtime_provider', 'frozen_runtime_config')
        with scope(config):
            provider = self.function('hermes_cli.runtime_provider', 'resolve_requested_provider')()
        return {'provider': provider, 'model': model,
                'effort': reasoning.get('effort') if reasoning.get('enabled', True) else 'none'}

    def stage(self, home, *, follows=False):
        """Native creation through completed policy capture, stopped before identity/DB publication.

        The authority stand-in supplies only admission and profile identity, never routing or config.
        No session row or running agent is claimed by this resolution proof.
        """
        authority = SimpleNamespace(profile_id=str(home), db=SimpleNamespace(db_path=str(home / 's3-unused.db')),
                                    _require_admission_open=lambda: None)
        actor = SimpleNamespace(profile_id=str(home), subject='hqr-native-probe', capabilities={'session:create'})
        stage = self.function('gateway.session_local', 'stage_local_session')
        boundary = self.function('gateway.session_local_recovery', 'local_identity')
        self.function('gateway.session_local', 'load_profile_config')
        self.function('gateway.session_policy', 'build_policy')
        captured = stop_at_call(lambda: stage(authority, actor, {'source': 'cli', 'cwd': str(home),
            'follow_profile_config': follows, 'request_id': 'hqr-native-probe'}), boundary)
        policy = captured['caller'].get('policy')
        ensure(policy is not None, 'native creation did not capture policy before identity')
        ensure(policy.follows_profile is follows, 'native following policy differs')
        return policy

    def policy_route(self, policy, home):
        self.function('gateway.session_policy', 'LocalSessionPolicy.effective')
        authority = SimpleNamespace(db=SimpleNamespace(db_path=str(home / 's3-unused.db')))
        config, model = policy.effective(authority, secrets=False)
        return self.route(config, model)

    def delegation(self, parent, expected, *, explicit_model=None):
        """Run the native per-task backend, stopping before credential resolution.

        The resolved backend route and native reasoning parser are the no-inference proof boundary.
        Do not supply a replacement credential bundle or instantiate an agent.
        """
        cfg = self.function('tools.delegate_tool_config', '_load_config')()
        ensure(cfg.get('backend') == 'model_map', 'native delegation backend is not model_map')
        try:
            active = self.function('tools.delegate_tool_routes', '_active_provider')(cfg)
        except ValueError as exc:
            raise ProbeFailure('native model_map backend unavailable; no child route can be proved') from exc
        self.plugin_function(type(active).task_parameters)
        self.plugin_function(type(active).route_task)
        declared = self.function('tools.delegate_tool_routes', '_declared_parameters')(active, cfg)
        parameters = [key for key, schema in declared.items() if 'general' in (schema.get('enum') or [])]
        ensure(len(parameters) == 1, 'native model_map general selector unavailable or ambiguous')
        task = {'goal': 'hqr native resolution only', parameters[0]: 'general'}
        if explicit_model is not None:
            ensure('model' in declared and parameters[0] != 'model',
                   'native backend exposes model as route selector, not an explicit model pin')
            task['model'] = explicit_model
        route = self.function('tools.delegate_tool_routes', '_route_one')(active, declared, 0, task, cfg)
        reasoning = self.function('tools.delegate_tool_config', '_child_reasoning')(parent, cfg, route.get('reasoning_effort'))
        actual = {'provider': route.get('provider'), 'model': route.get('model'),
                  'effort': reasoning.get('effort') if isinstance(reasoning, dict) else None}
        check_route(actual, expected)
        return {'route': actual, 'boundary': 'native backend route before credentials', 'selector': parameters[0]}


def check_fallback(events, verdict):
    ensure(verdict.get('qualified') is False, 'unqualified fallback requires an unqualified source verdict')
    evidence = events.native_evidence('hqr-probe', None, 'on_session_start')
    ensure(evidence.get('qualified') is False, 'product unexpectedly trusts the unqualified session source')
    # Real product attribution is exercised with delayed generations; no synthetic value is a native source claim.
    history = [{'generation': n, 'at': at, 'group': 'conversation', 'values': {}}
               for n, at in ((1, 100), (2, 200), (3, 300))]
    cases = {'delayed_A1_B_A2': {'started_at': 170}, 'capture_inside_window': {'started_at': 310},
             'changed_model': {'started_at': 370, 'changed_after_creation': True},
             'unknown_parent': {'started_at': 370, 'parent_type': 'unknown'}}
    observed = {}
    for name, fields in cases.items():
        observed[name] = events.generation_for(history, {**evidence, **fields}, 'conversation')
        ensure(observed[name] == {'state': 'geração indeterminada'}, 'AC-22 fallback reported a generation or age')
    return observed


def qualify_session_source(native, home, events):
    """Use ONLY a newly created native DB; never the target's state.db or a production DB."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix='s3-session-source-', dir=home) as directory:
        cls = native.function('hermes_state', 'SessionDB')
        native.function('hermes_state_sessions', 'SessionSessionsMixin.get_session')
        native.function('hermes_state_sessions', 'SessionSessionsMixin.create_session')
        native.function('hermes_state_sessions', 'SessionSessionsMixin.update_session_model')
        stage = native.function('gateway.session_local', 'stage_local_session')
        commit = native.function('hermes_state_local', 'commit_local_session')
        native.function('gateway.session_open', '_Open._deliver')
        db = cls(db_path=Path(directory) / 'probe.db')
        try:
            initial = {'model': 'gpt-6.1-sol', 'provider': 'openai-codex', 'reasoning_effort': 'xhigh'}
            db.create_session('hqr-source-probe', 'cli', model=initial['model'], model_config=initial)
            before = db.get_session('hqr-source-probe')
            ensure(isinstance(before, dict) and type(before.get('started_at')) in (int, float), 'native started_at missing')
            creation = decode_model_config(before.get('model_config'))
            ensure(creation == initial, 'native creation-time model_config missing')
            db.update_session_model('hqr-source-probe', 'claude-opus-5-5', provider='anthropic')
            after = db.get_session('hqr-source-probe')
            changed = decode_model_config(after.get('model_config')) != creation
            # A successful mutation disproves immutable creation data; no finite negative test proves immutability.
            verdict = source_verdict(started_stable=before['started_at'] == after['started_at'],
                                     model_config_immutable=False, capture_order=False)
            verdict['model_config_mutation_observed'] = changed
            stage_tree = ast.parse(inspect.getsource(stage))
            calls = {name: sorted(n.lineno for n in ast.walk(stage_tree) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == name)
                     for name in ('load_profile_config', '_now', 'build_policy')}
            ordered = all(calls.values()) and max(calls['load_profile_config']) < min(calls['build_policy']) < min(calls['_now'])
            verdict['capture_order'] = {'configuration_then_policy_then_clock': bool(ordered),
                                       'calls_in_stage': calls, 'commit_has_model_config': 'model_config' in inspect.getsource(commit)}
            verdict['reasons'] = ['creation_model_config_reader_not_qualified']
            if changed:
                verdict['reasons'].append('model_config_mutable')
            if not ordered:
                verdict['reasons'].append('capture_order_unproven')
            if not verdict['capture_order']['commit_has_model_config']:
                verdict['reasons'].append('local_creation_does_not_insert_model_config')
            verdict['fallback'] = check_fallback(events, verdict)
            verdict['reader'] = 'SessionDB.get_session: current mutable row, not immutable creation receipt'
            return verdict
        finally:
            db.close()


# Executed by the SAME host interpreter in a fresh exec; binding must precede runtime imports.
WORKER = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
snapshot = json.loads(sys.stdin.readline())
from agent.safe_worker_policy import _bind_worker_config
_bind_worker_config(snapshot)
from hermes_cli.config import load_config_readonly
from hermes_constants import resolve_reasoning_config
from tools.delegate_tool_config import _load_config
for line in sys.stdin:
    if line.strip() == 'close':
        break
    cfg = load_config_readonly()
    model = cfg['model']['default']
    reasoning = resolve_reasoning_config(cfg, model)
    print(json.dumps({'route': {'provider': cfg['model']['provider'], 'model': model,
        'effort': reasoning.get('effort') if reasoning.get('enabled', True) else 'none'},
        'delegation': _load_config()}), flush=True)
'''


class Worker:
    def __init__(self, native, guard, snapshot):
        native.function('agent.safe_worker_policy', '_bind_worker_config')
        native.function('hermes_cli.config', 'load_config_readonly')
        # The audit hook is installed in the child before any host import, too.
        # HQR-32 TEST-01: copied classes need their complete stdlib and failure dependencies.
        prefix = '\n'.join(inspect.getsource(value) for value in (ProbeFailure, UnsafeProbe, ensure, ProbeGuard))
        code = 'import os, stat, sys\nfrom contextlib import contextmanager\nfrom pathlib import Path\n' + prefix
        code += '\nguard = ProbeGuard(os.environ["HERMES_HOME"], missing_credentials=True)\nsys.addaudithook(guard.audit)\n' + WORKER
        argv = [sys.executable, '-I', '-B', '-c', code, str(native.root)]
        guard.workers.add(tuple(argv))
        # HQR-32: use the audited Popen fork/exec path even when Python supports spawn CLOSEFROM.
        # Keep direct os.posix_spawn forbidden; the worker gets its own session instead of a new guard capability.
        self.process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, start_new_session=True)
        self.process.stdin.write(json.dumps(snapshot) + '\n')
        self.process.stdin.flush()

    def read(self):
        import select
        self.process.stdin.write('probe\n')
        self.process.stdin.flush()
        ensure(select.select([self.process.stdout], [], [], 30)[0], 'native worker response timed out')
        line = self.process.stdout.readline()
        ensure(bool(line), 'native worker exited before resolution')
        try:
            return json.loads(line)
        except ValueError as exc:
            raise ProbeFailure('native worker did not return a JSON resolution') from exc

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.write('close\n')
                self.process.stdin.flush()
            except BrokenPipeError:
                pass
        try:
            _out, err = self.process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.communicate()
            raise ProbeFailure('native worker did not exit')
        ensure(self.process.returncode == 0 and not err.strip(), 'native worker exited unsuccessfully or emitted stderr')


class ConsumerProbe:
    """Prepare old consumers BEFORE Auto, resolve old/new consumers AFTER the first changed decision."""
    def __init__(self, home, *, guard=None):
        self.home = Path(home).resolve(strict=True)
        ensure(os.environ.get('HERMES_HOME') == str(self.home), 'HERMES_HOME must explicitly name the admitted target')
        self.guard = guard or ProbeGuard(self.home, missing_credentials=True)
        if guard is None:
            sys.addaudithook(self.guard.audit)
        self.native = NativeHost()
        self.guard.missing_roots.add(self.native.root)
        self.guard.readonly_commands.add((('git', 'rev-parse', 'HEAD'), str(self.native.root)))
        self.before = self.native.function('hermes_cli.config_backend', 'read_config_doc')(self.home / 'config.yaml')
        ensure(isinstance(self.before, dict), 'native profile is unreadable')
        self.old_route = self.native.route(self.before)
        self.dependency = case(self.native.load_delegation)
        self.old = case(lambda: self.native.stage(self.home))
        self.follow = case(lambda: self.native.stage(self.home, follows=True))
        self.old_worker = None
        self.old_worker_before = case(self.start_old_worker)

    def prepared(self, item):
        ensure(item['pass'], item.get('reason', 'before-decision preparation failed'))
        return item['observed']

    def start_old_worker(self):
        policy = self.prepared(self.old)
        config = self.native.function('gateway.session_managed_worker', '_worker_config')(
            SimpleNamespace(profile_id=str(self.home)), policy)
        self.old_worker = Worker(self.native, self.guard, config)
        result = self.old_worker.read()
        check_route(result['route'], self.old_route)
        return result

    def managed_old(self, status):
        before = self.prepared(self.old_worker_before)
        ensure('managed_sessions_created_before_decision' in status.get('coverage', {}).get('not_governed', []),
               'status does not mark old managed sessions out of coverage')
        if self.old_worker is None:
            raise ProbeFailure('old native worker was not prepared before decision')
        still_open = self.old_worker.read()
        check_route(still_open['route'], self.old_route)
        ensure(still_open['delegation'] == before['delegation'], 'old worker did not retain frozen delegation copy')
        frozen = self.native.function('gateway.session_managed_worker', '_worker_config')(
            SimpleNamespace(profile_id=str(self.home)), self.prepared(self.old))
        fresh = Worker(self.native, self.guard, frozen)
        try:
            actual = fresh.read()
            check_route(actual['route'], self.old_route)
            ensure(actual['delegation'] == before['delegation'], 'fresh worker did not inherit frozen delegation copy')
            return {'old_worker': before['route'], 'new_worker': actual['route'], 'frozen_delegation': True,
                    'status_out_of_coverage': True}
        finally:
            fresh.close()

    def managed_new(self, expected):
        policy = self.native.stage(self.home)
        config = self.native.function('gateway.session_managed_worker', '_worker_config')(
            SimpleNamespace(profile_id=str(self.home)), policy)
        worker = Worker(self.native, self.guard, config)
        try:
            result = worker.read()
            ensure(result['delegation'] == self.native.function('tools.delegate_tool_config', '_load_config')(),
                   'new managed worker did not capture decided delegation config')
            return check_route(result['route'], expected)
        finally:
            worker.close()

    def cron(self, expected, status_fn):
        read = self.native.function('hermes_cli.config_backend', 'read_config_doc')
        write = self.native.function('hermes_cli.config_backend', 'write_changes')
        changes = self.native.function('hermes_cli.config_backend', 'Changes')
        load = self.native.function('cron.scheduler', '_load_cron_job_config')
        runtime = self.native.function('cron.scheduler', '_resolve_job_runtime')
        boundary = self.native.function('hermes_cli.runtime_provider', 'resolve_runtime_provider')
        resolve_provider = self.native.function('hermes_cli.runtime_provider', 'resolve_requested_provider')
        scope = self.native.function('hermes_cli.runtime_provider', 'frozen_runtime_config')
        effort = self.native.function('cron.scheduler', '_resolve_job_reasoning_config')
        path = self.home / 'config.yaml'
        baseline = read(path)
        cases = [('conversation', {}, {}, expected, False),
            ('complete', {'model': 'gpt-6.1-terra', 'model_provider': 'openai-codex'}, {},
             {'provider': 'openai-codex', 'model': 'gpt-6.1-terra', 'effort': expected['effort']}, False),
            ('model_override', {'model': 'gpt-6.1-terra', 'model_provider': 'openai-codex'}, {'gpt-6.1-terra': 'low'},
             {'provider': 'openai-codex', 'model': 'gpt-6.1-terra', 'effort': 'low'}, False),
            ('partial_model', {'model': 'gpt-6.1-terra'}, {},
             {**expected, 'model': 'gpt-6.1-terra'}, True),
            ('partial_provider', {'model_provider': 'openai-codex'}, {}, {**expected, 'provider': 'openai-codex'}, True)]
        expected_origins = {
            'conversation': ('conversation', 'conversation', 'agent.reasoning_effort'),
            'complete': ('cron.model', 'cron.model_provider', 'agent.reasoning_effort'),
            'model_override': ('cron.model', 'cron.model_provider', 'agent.reasoning_overrides'),
            'partial_model': ('cron.model', 'conversation', 'agent.reasoning_effort'),
            'partial_provider': ('conversation', 'cron.model_provider', 'agent.reasoning_effort')}
        observed = {}
        try:
            for label, cron, overrides, wanted, partial in cases:
                document = json.loads(json.dumps(baseline))
                document['cron'] = cron
                document.setdefault('agent', {})['reasoning_overrides'] = overrides
                write(path, changes(document=document))
                jc = load({}, 'hqr-native-probe', 'synthetic resolution only')
                request = stop_at_call(lambda: runtime({}, 'hqr-native-probe', jc), boundary)['callee']
                with scope(jc.cfg):
                    provider = resolve_provider(request.get('requested'))
                reasoning = effort({}, jc.cfg, jc.model)
                actual = check_route({'provider': provider, 'model': jc.model, 'effort': reasoning.get('effort')}, wanted)
                ensure(request.get('target_model') == jc.model, 'native cron runtime uses a different model')
                status = status_fn()
                origin = status.get('cron_origins', {}).get('default', {})
                ensure(origin.get('partial') is partial, 'status partial cron classification differs')
                for key, source in zip(('model', 'provider', 'effort'), expected_origins[label]):
                    ensure(origin.get(key, {}).get('value') == actual[key], 'status cron value differs from native resolution: ' + key)
                    ensure(origin.get(key, {}).get('origin') == source, 'status cron origin differs: ' + key)
                if label == 'model_override':
                    ensure(actual['effort'] != expected['effort'], 'cron override did not differ from conversation effort')
                observed[label] = {'route': actual, 'origins': origin,
                                   'boundary': 'native scheduler runtime request before credentials'}
            return observed
        finally:
            write(path, changes(document=baseline))

    def cron_jobs(self, expected, status_fn, *, partial):
        read = self.native.function('hermes_cli.config_backend', 'read_config_doc')
        load = self.native.function('cron.scheduler', '_load_cron_job_config')
        runtime = self.native.function('cron.scheduler', '_resolve_job_runtime')
        boundary = self.native.function('hermes_cli.runtime_provider', 'resolve_runtime_provider')
        effort = self.native.function('cron.scheduler', '_resolve_job_reasoning_config')
        path = self.home / 'cron' / 'jobs.json'
        prior = path.read_bytes() if path.exists() else None
        job = {'id': 'hqr-pin-proof', 'provider': 'openai-codex', 'reasoning_effort': 'low'}
        if not partial:
            job.update(model='gpt-6.1-terra', base_url='http://127.0.0.1:1/v1')
        path.parent.mkdir(exist_ok=True)
        try:
            path.write_text(json.dumps({'jobs': [job]}))
            before = path.read_bytes()
            config = read(self.home / 'config.yaml')
            wanted = {'provider': job['provider'], 'model': expected['model'] if partial else job['model'], 'effort': 'low'}
            jc = load(job, job['id'], 'synthetic pin proof')
            request = stop_at_call(lambda: runtime(job, job['id'], jc), boundary)['callee']
            actual = check_route({'provider': request.get('requested'), 'model': jc.model,
                                  'effort': effort(job, jc.cfg, jc.model).get('effort')}, wanted)
            if not partial:
                ensure(request.get('explicit_base_url') == job['base_url'], 'complete job endpoint lost')
            status = status_fn()
            row = next(r for r in status['cron_origins']['jobs'] if r['job'] == job['id'])
            ensure(row['partial'] is partial, 'job partial classification differs')
            for key in ('provider', 'model', 'effort'):
                ensure(row[key]['value'] == actual[key], 'job status differs from native resolution: ' + key)
            ensure(path.read_bytes() == before, 'Auto changed the pinned jobs file')
            ensure(read(self.home / 'config.yaml') == config, 'pin-only proof changed profile config')
            return {'route': actual, 'status': row, 'jobs_unchanged': True}
        finally:
            if prior is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(prior)

    def explicit(self, expected):
        """Complete native switch + session persistence/resume and explicit delegation route, never a chat."""
        read = self.native.function('hermes_cli.config_backend', 'read_config_doc')
        write = self.native.function('hermes_cli.config_backend', 'write_changes')
        changes = self.native.function('hermes_cli.config_backend', 'Changes')
        path = self.home / 'config.yaml'
        baseline = read(path)
        stub = MetadataStub(self.guard)
        db = None
        try:
            # All metadata and this provider are synthetic; neither catalog nor key is copied from the host.
            local = {'name': 'HQR proof', 'base_url': stub.url + '/v1', 'models': ['hqr-explicit']}
            options = baseline['delegation']['backends']['model_map']['options']
            explicit = {'name': 'explicit', 'description': 'Synthetic explicit model', 'model': 'hqr-explicit',
                        'base_url': stub.url + '/v1', 'reasoning_effort': 'low'}
            write(path, changes(set={'models_dev.url': stub.url + '/models-dev.json', 'providers.hqr-proof': local,
                                    'delegation.backends.model_map.options': [*options, explicit]}))
            parser = self.native.function('hermes_cli.model_switch', 'parse_model_switch_args')
            parsed = parser('hqr-explicit --provider hqr-proof --reasoning low --session')
            ensure(parsed.is_session and not parsed.is_global and not parsed.errors, 'native /model scope did not stay session-only')
            switch = self.native.function('hermes_cli.model_switch', 'switch_model')
            result = switch(raw_input=parsed.target, current_model=expected['model'], current_provider=expected['provider'],
                            explicit_provider=parsed.explicit_provider, user_providers={'hqr-proof': local}, is_global=False)
            ensure(result.success, 'native switch_model refused the credential-free local route')
            ensure(result.new_model == 'hqr-explicit' and result.base_url == stub.url + '/v1' and not result.is_global,
                   'native explicit /model lost its model, endpoint or scope')
            cls = self.native.function('hermes_state', 'SessionDB')
            db = cls(db_path=self.home / 'explicit-session-probe.db')
            db.create_session('hqr-explicit-session', 'cli', model=expected['model'], model_config=expected)
            session = SimpleNamespace(_session_db=db, session_id='hqr-explicit-session')
            persist = self.native.function('hermes_cli.cli_model_switch_mixin', 'CLIModelSwitchMixin._persist_model_switch_to_session')
            persist(session, result)
            row = db.get_session('hqr-explicit-session')
            restore = self.native.function('hermes_cli.cli_model_switch_mixin', 'stored_session_route')
            resumed = restore(row, current_model=expected['model'], current_provider=expected['provider'])
            ensure(row['model'] == 'hqr-explicit' and resumed is not None, 'native /model session commit missing')
            ensure(resumed[0] == 'hqr-explicit' and resumed[1] == result.target_provider and resumed[2] == stub.url + '/v1',
                   'native resume replaced explicit session route with profile decision')
            # Model-map exposes named model selection, not a raw model parameter.
            parent = SimpleNamespace(model=expected['model'], provider=expected['provider'], base_url=None,
                                     reasoning_config={'enabled': True, 'effort': expected['effort']})
            cfg = self.native.function('tools.delegate_tool_config', '_load_config')()
            routes, error = self.native.function('tools.delegate_tool_routes', 'resolve_task_routes')(
                [{'goal': 'resolution only', 'option': 'explicit'}], cfg, parent)
            ensure(error is None and len(routes) == 1 and routes[0].error is None, 'native explicit backend call refused')
            route = routes[0]
            reasoning = self.native.function('tools.delegate_tool_config', '_child_reasoning')(parent, cfg, route.reasoning_effort)
            actual = check_route({'provider': route.creds['provider'], 'model': route.creds['model'], 'effort': reasoning['effort']},
                                 {'provider': 'custom', 'model': 'hqr-explicit', 'effort': 'low'})
            ensure(route.creds['base_url'] == stub.url + '/v1', 'explicit backend endpoint lost')
            # Trusted native callers can also pin a raw model per delegate_task call.
            delegate = self.native.function('tools.delegate_tool', 'delegate_task')
            boundary = self.native.function('tools.delegate_tool', '_build_children')
            captured = stop_at_call(lambda: delegate(goal='resolution only', parent_agent=parent,
                credentials_cfg={'model': 'hqr-explicit', 'base_url': stub.url + '/v1', 'reasoning_effort': 'low'}), boundary)
            pin = captured['callee']['routes'][0]
            ensure(pin.creds['model'] == 'hqr-explicit' and pin.creds['provider'] == 'custom', 'explicit delegate_task model lost')
            ensure(read(path)['model'] == baseline['model'], 'session choice wrote profile model')
            ensure(stub.requests and all(r['method'] == 'GET' for r in stub.requests), 'metadata stub was not exercised safely')
            return {'session_commit': {'model': row['model'], 'provider': resumed[1], 'session_only': True},
                    'subagent_backend': actual, 'explicit_delegate_call': {'model': pin.creds['model'], 'provider': pin.creds['provider']},
                    'metadata_requests': stub.requests, 'profile_unchanged': True,
                    'boundary': 'native switch result, persisted session resume and delegation before child construction; no inference'}
        finally:
            if db is not None:
                db.close()
            try:
                write(path, changes(document=baseline))
            finally:
                stub.close()

    def after(self, expected, delegated, status_fn, events):
        scenarios = {}
        try:
            status = status_fn()
            ensure(self.old_route != expected, 'consumer proof requires a changed Auto decision')
            actual = self.native.route(self.native.function('hermes_cli.config_backend', 'read_config_doc')(self.home / 'config.yaml'))
            check_route(actual, expected)
            scenarios['C1'] = case(lambda: check_route(self.native.policy_route(self.native.stage(self.home), self.home), expected))
            scenarios['C2'] = case(lambda: check_route(self.native.policy_route(self.prepared(self.old), self.home), self.old_route))
            scenarios['C3'] = case(lambda: check_route(self.native.policy_route(self.prepared(self.follow), self.home), expected))
            def delegation():
                self.prepared(self.dependency)
                results = {}
                for name, policy in [('already_open', self.prepared(self.old)), ('new', self.native.stage(self.home))]:
                    parent_route = self.native.policy_route(policy, self.home)
                    parent = SimpleNamespace(model=parent_route['model'], provider=parent_route['provider'],
                                             reasoning_config={'enabled': True, 'effort': parent_route['effort']})
                    results[name] = self.native.delegation(parent, delegated)
                return results
            scenarios['C4'] = case(delegation)
            scenarios['C5'] = case(lambda: self.managed_old(status))
            scenarios['C6'] = case(lambda: self.managed_new(expected))
            scenarios['C7'] = case(lambda: self.cron(expected, status_fn))
            scenarios['C8'] = case(lambda: self.cron_jobs(expected, status_fn, partial=False))
            scenarios['C9'] = case(lambda: self.cron_jobs(expected, status_fn, partial=True))
            scenarios['C10'] = case(lambda: self.explicit(expected))
            scenarios['AC-22'] = case(lambda: qualify_session_source(self.native, self.home, events))
        finally:
            if self.old_worker is not None:
                self.old_worker.close()
        return {'scenarios': scenarios, 'pending_consumer_proofs': [n + ': ' + scenarios.get(n, {}).get('reason', 'native proof missing') for n in REQUIRED if not scenarios.get(n, {}).get('pass')],
                'native_sources': self.native.sources, 'host_source_root': str(self.native.root), 'advanced_delegation': self.dependency,
                'proof_scope': 'native config/policy resolution, not inference, authentication or full session publication',
                'audit_denied': self.guard.denied, 'absent_credentials_blocked': len(self.guard.absent_credentials)}
