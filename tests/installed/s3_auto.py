"""S3 installed runner for the admitted target; not executed by local suites.

Usage: python3 tests/installed/s3_auto.py <new receipts> --candidate <SHA40> --rollback <SHA40> --advanced-manifest <reviewed.json>
Revision changes always require effective OFF, disable, safe scan, force install, exact files, enable and smoke.
The candidate must already include a separately qualified Docker-host fingerprint; this runner never enrolls a host.
No inference, credential lookup, real-Hermes configuration read or service restart is part of this runner.
HQR-32 attested dependency reuse is recorded in decisions/s3-delivery.md.
HQR-38 adds the safety net group proof (decisions/hqr-38-delivery.md); it was not executed on an installed target.
"""
import json
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lifecycle import GITHUB, ORIGIN, PLUGIN, SCAN, TARGET, Failure, check, deployment, installed_modules, listener_admission, require_safe_scan, single
from s2_observe import S2Run, STATE, VOLUME, TASK_LABEL, inactive, parse, require_off
from s3_native_consumers import require_complete

ADVANCED_VERSION = '1.1.0'
ADVANCED_REF = '13b2c1c9c8204bf333df240b2aacf98c3e6250b7'
ADVANCED_ORIGIN = 'https://github.com/NousResearch/hermes-official-plugins#advanced-delegation'

NATIVE_SOURCE = Path(__file__).with_name('s3_native_consumers.py').read_text(encoding='utf-8')
NATIVE_BOOTSTRAP = '''
import linecache, os, sys, types
from pathlib import Path
_source = %r
_filename = '<hqr-s3-native-consumers>'
_native = types.ModuleType('hqr_s3_native_consumers')
_native.__file__ = _filename
sys.modules[_native.__name__] = _native
linecache.cache[_filename] = (len(_source), None, _source.splitlines(True), _filename)
exec(compile(_source, _filename, 'exec'), _native.__dict__)
_guard = _native.ProbeGuard(os.environ['HERMES_HOME'], missing_credentials=True)
os.open = _guard.wrap_open(os.open)
sys.addaudithook(_guard.audit)
os.environ['HERMES_DISABLE_LAZY_INSTALLS'] = '1'
os.environ['GIT_NO_LAZY_FETCH'] = '1'
os.environ['GIT_OPTIONAL_LOCKS'] = '0'
os.environ['GIT_TERMINAL_PROMPT'] = '0'
_root = _native.NativeHost().root
_guard.missing_roots.add(_root)
_guard.readonly_commands.add((('git', 'rev-parse', 'HEAD'), str(_root)))
''' % NATIVE_SOURCE


ADVANCED_CHECK = NATIVE_BOOTSTRAP + r"""
import json, sys
from tools.plugin_guard import scan_plugin
from hermes_cli.config_backend import read_config_doc
from hermes_cli.config import get_config_path
expected = json.loads(sys.stdin.read())
root = Path(os.environ['HERMES_HOME']) / 'plugins' / 'advanced-delegation'
result = _native.dependency_inventory(root, expected['files'])
# SEC-S3-06: admit only the scanner's read-only index query, not general native subprocesses.
with _guard.scanner_git(root):
    scan = scan_plugin(root, source=expected['ref'])
result['verdict'] = scan.verdict
config = read_config_doc(get_config_path()) or {}
result['scan_on_install'] = config.get('plugins', {}).get('scan_on_install', True)
if expected.get('reuse'):
    from hermes_cli.plugins_cmd_git import pinned_revision
    result['pin'] = pinned_revision('advanced-delegation')
print(json.dumps(result))
"""


def install_advanced(run):
    expected = getattr(run, 'advanced_manifest', None)
    check(isinstance(expected, dict) and expected.get('ref') == ADVANCED_REF and expected.get('files'),
          'reviewed advanced-delegation byte manifest required before install')
    reused = False
    try:
        run.hermes('plugins', 'install', ADVANCED_ORIGIN, '--ref', ADVANCED_REF, '--no-enable')
    except Failure as exc:
        # HQR-32 RUN-01: only the inspected native existing-destination refusal permits attested reuse.
        if "Plugin 'advanced-delegation' already exists. Use force reinstall" not in str(exc):
            raise
        reused = True
        check(inactive(run.hermes('plugins', 'show', 'advanced-delegation').stdout),
              'advanced-delegation reuse requires not enabled')
    attested = run.json(ADVANCED_CHECK, stdin=json.dumps(dict(expected, reuse=True) if reused else expected))
    if reused:
        check(attested.get('pin') == ADVANCED_REF, 'advanced-delegation reuse pin differs', attested)
    check(attested.get('bytes_match') is True and attested.get('special') == [] and attested.get('scan_on_install') is not False,
          'advanced-delegation tree or scan policy differs', attested)
    require_safe_scan(attested)
    run.hermes('plugins', 'enable', 'advanced-delegation')
    result = run.json(NATIVE_BOOTSTRAP + '''
import json
native = _native.NativeHost()
result = native.load_delegation()
from hermes_cli.plugins_cmd_git import pinned_revision
assert pinned_revision('advanced-delegation') == '13b2c1c9c8204bf333df240b2aacf98c3e6250b7'
print(json.dumps(result))
''')
    check(result['version'] == ADVANCED_VERSION and result['backend'] == 'model_map', 'advanced-delegation runtime differs', result)
    return dict(result, ref=ADVANCED_REF, reused=reused)


def swap_revision(revision, callbacks):
    observations = {}
    for gate in ('off', 'disable', 'scan', 'install', 'files', 'enable', 'smoke'):
        observations[gate] = callbacks[gate](revision)
    return observations


# Synthetic usage is injected only inside this installed test process, never through a plugin test endpoint.
EXERCISE = NATIVE_BOOTSTRAP + r'''
import copy, hashlib, importlib, json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from hermes_cli.plugins import get_plugin_command_handler
from hermes_cli.config import get_config_path
from hermes_cli.config_backend import Changes, read_config_doc, write_changes
from hermes_constants import resolve_reasoning_config
handler = get_plugin_command_handler('quota-router')
assert handler is not None
manager = handler.__self__
assert manager.compatible()['ok'], manager.compatible()
path = get_config_path()
original = read_config_doc(path)
assert isinstance(original, dict)
for key in ('api_key', 'api', 'key_env', 'api_key_env', 'context_length', 'model', 'name'):
    assert key not in original.get('model', {}), key
before = copy.deepcopy(original)
groups = importlib.import_module(manager.__module__.rsplit('.', 1)[0] + '.groups')
routes = importlib.import_module(manager.__module__.rsplit('.', 1)[0] + '.routes')
# D18: target-only fixture uses the fingerprint-bound native route, not an endpoint-free shortcut.
def prepare_native_routes():
    native = routes.defaults('openai-codex')
    write_changes(path, Changes(set={'model.default': 'gpt-6.1-sol', 'model.provider': 'openai-codex',
        'model.base_url': native['base_url'], 'model.api_mode': native['api_mode'],
        'agent.reasoning_effort': 'low', 'delegation.backend': 'model_map', 'delegation.backends.model_map.options': [
          {'name': 'general', 'description': 'Synthetic general role', 'provider': 'openai-codex', 'model': 'gpt-6.1-sol',
           **native, 'reasoning_effort': 'medium', 'fallbacks': []}]}))
prepare_native_routes()
base = copy.deepcopy(read_config_doc(path))
now = datetime.now(timezone.utc)
usage = {'openai-codex': 100, 'anthropic': 10}
def snapshot(provider):
    current = datetime.now(timezone.utc)
    label = 'Weekly' if provider == 'openai-codex' else 'Current week'
    window = SimpleNamespace(label=label, used_percent=usage[provider], reset_at=now + timedelta(hours=72), scope='account')
    return SimpleNamespace(provider=provider, source='usage_api' if provider == 'openai-codex' else 'oauth_usage_api',
      fetched_at=current, windows=(window,), unavailable_reason=None,
      raw={'rate_limit': {'primary_window': {'limit_window_seconds': 604800}, 'allowed': usage[provider] < 100,
                          'limit_reached': usage[provider] >= 100},
           'credits': {'has_credits': True, 'balance': '12.50', 'overage_limit_reached': False},
           'spend_control': {'reached': False}} if provider == 'openai-codex' else None)
manager.importer = lambda: snapshot
manager.cache.clear()
def command(text):
    value = json.loads(handler(text + ' --json'))
    assert value['ok'], value.get('error')
    return value
def rest(doc):
    data = copy.deepcopy(doc)
    (data.get('plugins') or {}).get('entries', {}).pop('hermes-quota-router', None)
    return data
observations = {}
command('mode observe')
command('config approve-map base')
observed_before = rest(read_config_doc(path))
observe = command('explain')
assert observe['decisions']['conversation']['choice'] == 'anthropic'
assert rest(read_config_doc(path)) == observed_before
observations['AC-17'] = True
consumers = _native.ConsumerProbe(path.parent, guard=_guard)
auto = command('mode auto')
for role in ('conversation', 'general'):
    selected = dict(manager.settings()[0]['roles'][role]['anthropic'], provider='anthropic')
    assert groups.project(read_config_doc(path), role) == groups.target(role, selected)
    assert role not in auto['applied']['groups_out']
    preview = observe['decisions']['conversation'] if role == 'conversation' else observe['decisions']['routes'][role]
    assert preview['choice'] == 'anthropic'
    assert preview['would_change']['to'] == selected
observations['native-default-route-apply'] = True
events = importlib.import_module(manager.__module__.rsplit('.', 1)[0] + '.events')
observations['consumers'] = consumers.after(
    {'provider': 'anthropic', 'model': 'claude-opus-5-5', 'effort': 'high'},
    {'provider': 'anthropic', 'model': 'claude-opus-5-5', 'effort': 'medium'}, lambda: command('status'), events)
def quota_error():
    import uuid
    invoke = consumers.native.function('hermes_cli.plugins', 'invoke_hook')
    session_id = 'synthetic-quota-task-' + uuid.uuid4().hex
    manager.wait_hooks()
    before = manager.engine.read_record('events.json', [])
    emitted_at = manager.clock().timestamp()
    invoke('api_request_error', provider='anthropic', model='claude-opus-5-5',
           error={'type': 'QuotaExhausted', 'message': 'SYNTHETIC_PRIVATE_ERROR'}, session_id=session_id)
    manager.wait_hooks()
    records = manager.engine.read_record('events.json', [])
    salt = manager.engine.read_record('salt.json')
    assert isinstance(salt, str), 'current hook did not establish redaction salt'
    digest = hashlib.sha256((salt + session_id).encode()).hexdigest()
    assert not any(r.get('session_id_hash') == digest for r in before), 'correlation already existed before emission'
    matches = [r for r in records if r.get('session_id_hash') == digest]
    assert len(matches) == 1, 'current hook emission has no unique new record'
    record = matches[0]
    assert (record.get('event'), record.get('provider'), record.get('model'), record.get('error_class')) == (
        'api_request_error', 'anthropic', 'claude-opus-5-5', 'QuotaExhausted')
    assert record['at'] >= emitted_at, 'current record predates emission watermark'
    assert set(record) == {'event', 'at', 'provider', 'model', 'error_class', 'session_id_hash', 'decision'}
    serialized = json.dumps(records)
    assert session_id not in serialized and 'SYNTHETIC_PRIVATE_ERROR' not in serialized
    return {'recorded': True, 'session_id_hash': digest, 'emitted_at': emitted_at, 'recorded_at': record['at'],
            'coverage': command('status')['coverage']['hooks']}
observations['consumers']['scenarios']['C12'] = _native.case(quota_error)
command('config set credits.openai-codex false')
for name, codex_used, claude_used, expected in [('A2', 100, 10, 'anthropic'), ('A3', 10, 100, 'openai-codex'),
                                               ('A5', 100, 100, None), ('A13', 5, 10, 'openai-codex')]:
    usage.update({'openai-codex': codex_used, 'anthropic': claude_used})
    manager.cache.clear()
    prior = copy.deepcopy(read_config_doc(path))
    result = command('apply')
    current = read_config_doc(path)
    if expected is None:
        assert rest(current) == rest(prior)
    else:
        assert current['model']['provider'] == expected
        effort = 'xhigh' if expected == 'openai-codex' else 'high'
        assert resolve_reasoning_config(current, current['model']['default']) == {'enabled': True, 'effort': effort}
    observations[name] = True
# Re-establish Claude preference, then prove route writes below, at and above hysteresis.
groups = importlib.import_module(manager.__module__.rsplit('.', 1)[0] + '.groups')
usage.update({'openai-codex': 100, 'anthropic': 20})
manager.cache.clear()
command('apply')
for used, expected_route in ((15, 'anthropic'), (12, 'anthropic'), (11, 'openai-codex')):
    usage.update({'openai-codex': used, 'anthropic': 20})
    for _ in range(3):
        manager.cache.clear()
        command('apply')
        persisted = read_config_doc(path)
        roles = manager.settings()[0]['roles']
        assert groups.project(persisted, 'general') == groups.target('general', dict(roles['general'][expected_route], provider=expected_route))
        assert groups.project(persisted, 'conversation') == groups.target('conversation', dict(roles['conversation']['openai-codex'], provider='openai-codex'))
observations['A13-route-hysteresis'] = True
mapping = importlib.import_module(manager.__module__.rsplit('.', 1)[0] + '.mapping')
assert mapping.model_gate('claude-fable-5-2') and mapping.model_gate('gpt-6-astra')
observations['B3-B4'] = True
# Native cron resolver confirms model-dependent override precedence, separate from conversation effort.
from cron.scheduler import _resolve_job_reasoning_config
cfg = copy.deepcopy(read_config_doc(path))
assert _resolve_job_reasoning_config({}, cfg, cfg['model']['default']) == resolve_reasoning_config(cfg, cfg['model']['default'])
cfg.setdefault('agent', {})['reasoning_overrides'] = {'gpt-6.1-terra': 'low'}
assert _resolve_job_reasoning_config({}, cfg, 'gpt-6.1-terra') == {'enabled': True, 'effort': 'low'}
assert _resolve_job_reasoning_config({'reasoning_effort': 'max'}, cfg, 'gpt-6.1-terra') == {'enabled': True, 'effort': 'max'}
observations['C7-effort'] = True
# A single external field excludes its entire group and is never overwritten on OFF.
write_changes(path, Changes(set={'model.default': 'gpt-6.1-terra'}))
changed = command('apply')
assert 'conversation' in changed['applied']['groups_out']
command('mode off')
assert read_config_doc(path)['model']['default'] == 'gpt-6.1-terra'
observations['D7-OFF'] = True
# Restore test setup through the native writer; Auto is OFF before preparing a new enrollment.
reset = copy.deepcopy(base)
reset['plugins'] = copy.deepcopy(read_config_doc(path)['plugins'])
write_changes(path, Changes(document=reset))
command('mode auto')
# Actual native writes interrupted after journal publication, followed by fresh-engine recovery.
engine = manager.engine
selected = {'provider': 'anthropic', 'model': 'claude-opus-5-5', 'effort': 'high'}
def interrupt(point):
    if point == 'written':
        raise RuntimeError('synthetic interrupted write')
engine.checkpoint = interrupt
try:
    engine.cycle({'general': selected}, enabled={'general', 'conversation'}, now=datetime.now(timezone.utc).timestamp())
except RuntimeError:
    pass
finally:
    engine.checkpoint = lambda _point: None
prior_baseline = copy.deepcopy(engine.state['groups']['general']['baseline'])
prior_generation = engine.state['generation']
assert engine.recover()
groups = importlib.import_module(manager.__module__.rsplit('.', 1)[0] + '.groups')
assert groups.project(read_config_doc(path), 'general') == groups.target('general', selected)
assert engine.state['groups']['general']['last'] == groups.target('general', selected)
assert engine.state['groups']['general']['baseline'] == prior_baseline
assert engine.state['generation'] == prior_generation + 1
observations['D10-native-recovery'] = True
command('mode off')
assert rest(read_config_doc(path)) == rest(base)
observations['D3'] = True
for key, value in routes.defaults('openai-codex').items():
    assert read_config_doc(path)['model'][key] == value
    assert groups.option(read_config_doc(path), 'general')[key] == value
observations['native-default-route-restore'] = True
# HQR-38 D-28/D-29: native readers of the written chains; the same functions are bound in compat.SAFETY_NET.
def native_chain(document, role):
    from hermes_cli.fallback_config import get_fallback_chain, scoped_fallback_chain
    if role == 'conversation':
        return get_fallback_chain(document)
    from tools.delegate_tool_routes import _with_inherited_fallback
    route = _with_inherited_fallback(groups.option(document, role), (document.get('delegation') or {}))
    return scoped_fallback_chain(None, route.get('fallback_providers'), pinned=True, owner='delegation') or []
# HQR-38 acceptance: safety net groups at root and per route, closed projection, readback, exact OFF and external edit.
def prove_safety_net_groups(native_chain):
    roles = ('conversation', 'general')
    def node(document, role):
        if role == 'conversation':
            return document
        return next(o for o in document['delegation']['backends']['model_map']['options'] if o.get('name') == role)
    def install(document):
        current = read_config_doc(path)
        if 'plugins' in current:
            document['plugins'] = copy.deepcopy(current['plugins'])
        write_changes(path, Changes(document=document))
        return copy.deepcopy(read_config_doc(path))
    command('mode off')
    setup = copy.deepcopy(read_config_doc(path))
    for role in roles:
        node(setup, role).pop('fallback_providers', None)
    proofs = {}
    for case, value in (('absent', None), ('present', [])):
        baseline = copy.deepcopy(setup)
        if value is not None:
            for role in roles:
                node(baseline, role)['fallback_providers'] = copy.deepcopy(value)
        expected = install(baseline)
        manager.cache.clear()
        auto = command('mode auto')
        current = read_config_doc(path)
        status = command('status')
        decisions = {'conversation': auto['decisions']['conversation'], 'general': auto['decisions']['routes']['general']}
        for role in roles:
            name = groups.fallback_group(role)
            chain = decisions[role]['safety_net']['chain']
            assert chain, name + ': the peer provider must be Free for this proof'
            assert all({'provider', 'model'} <= set(entry) <= set(groups.ENTRY_FIELDS) for entry in chain), name
            assert node(current, role)['fallback_providers'] == chain, name
            projection = groups.project(current, name)
            assert projection == {'fallback_providers': {'present': True, 'value': chain}}, name
            assert groups.validate_projection(name, projection) == projection, name
            assert native_chain(current, role) == chain, name + ': native reader differs from the written chain'
            assert status['applied']['safety_net'][name]['active'] is True, name
            assert name not in status['applied']['groups_out'], name
        proofs['apply-readback'] = True
        command('mode off')
        restored = read_config_doc(path)
        assert rest(restored) == rest(expected), 'OFF did not restore the ' + case + ' baseline exactly'
        for role in roles:
            assert ('fallback_providers' in node(restored, role)) == (value is not None), role
        proofs['off-restore-' + case] = True
    # A human edit of the root chain excludes only its safety net group and survives OFF.
    expected = install(copy.deepcopy(setup))
    manager.cache.clear()
    command('mode auto')
    edited = [{'provider': 'openai-codex', 'model': 'gpt-6.1-terra'}]
    write_changes(path, Changes(set={'fallback_providers': edited}))
    manager.cache.clear()
    changed = command('apply')
    assert changed['applied']['groups_out'].get('fallback:conversation') == ['fallback_providers']
    assert 'conversation' not in changed['applied']['groups_out']
    assert read_config_doc(path)['fallback_providers'] == edited
    command('mode off')
    final = read_config_doc(path)
    assert final['fallback_providers'] == edited
    assert 'fallback_providers' not in node(final, 'general')
    expected['fallback_providers'] = edited
    assert rest(final) == rest(expected)
    proofs['external-edit-exclusion'] = True
    install(copy.deepcopy(setup))
    return proofs
# Both peers Free so each role gets a non-empty chain.
usage.update({'openai-codex': 10, 'anthropic': 20})
manager.cache.clear()
observations['safety-net-groups'] = prove_safety_net_groups(native_chain)
# D18/AC-17: a custom route is excluded in Observe and Auto, including OFF; never disclose its value.
def prove_custom_route_refusal():
    command('mode off')
    baseline = copy.deepcopy(read_config_doc(path))
    write_changes(path, Changes(set={'model.base_url': 'https://synthetic.invalid/custom-route'}))
    before = copy.deepcopy(read_config_doc(path)['model'])
    command('mode observe')
    preview = command('explain')
    assert preview['decisions']['conversation']['choice'] is None
    assert preview['decisions']['conversation'].get('would_change') is None
    assert preview['decisions']['conversation']['blocked_fields'] == ['model.base_url']
    auto = command('mode auto')
    assert auto['decisions']['conversation'].get('choice') is None
    assert auto['decisions']['conversation'].get('would_change') is None
    assert auto['applied']['groups_out']['conversation'] == ['model.base_url']
    assert read_config_doc(path)['model'] == before
    command('mode off')
    assert read_config_doc(path)['model'] == before
    current = read_config_doc(path)
    if 'plugins' in current:
        baseline['plugins'] = copy.deepcopy(current['plugins'])
    write_changes(path, Changes(document=baseline))
    assert read_config_doc(path)['model'] == baseline['model']
    return True
observations['custom-route-refusal'] = prove_custom_route_refusal()
# Leave a declared Auto marker so the outer runner can exercise disable/re-enable absence.
command('mode auto')
observations['pending_consumer_proofs'] = observations['consumers']['pending_consumer_proofs']
print(json.dumps(observations, sort_keys=True))
'''

COMPAT = r'''
import importlib, json
from hermes_cli.plugins import get_plugin_command_handler
handler = get_plugin_command_handler('quota-router')
assert handler is not None
manager = handler.__self__
compat = importlib.import_module(manager.__module__.rsplit('.', 1)[0] + '.compat')
print(json.dumps(compat.native_compatibility(), sort_keys=True))
'''


def require_removable(status):
    applied = status.get('applied') or {}
    check(status.get('ok') is True and status.get('mode_saved') == 'off' and status.get('mode_effective') == 'off' and
          applied.get('auto_declared') is not True and not any(e.get('active') for e in applied.get('groups', {}).values()),
          'product flow refuses removal until effective OFF and baseline restoration')


def product_remove(run):
    status = single(run.probe('status'))
    require_removable(status)
    return run.hermes('plugins', 'remove', PLUGIN)


READ_PROFILE = """
import json
from hermes_cli.config import get_config_path
from hermes_cli.config_backend import read_config_doc
print(json.dumps(read_config_doc(get_config_path())))
"""


def absence_projection(document):
    import copy
    result = copy.deepcopy(document)
    plugins = result.get('plugins', {})
    for key in ('enabled', 'disabled'):
        plugins[key] = [name for name in plugins.get(key, []) if name != PLUGIN]
    return result


def validate_target(info, volume):
    host, config = info['HostConfig'], info['Config']
    check(config['User'] == '10001:10001' and (config.get('Labels') or {}).get('hqr.task') == TASK_LABEL, 'target identity differs')
    check(host['CapDrop'] == ['ALL'] and not host['CapAdd'] and not host['Privileged'] and
          'no-new-privileges=true' in (host['SecurityOpt'] or []), 'target privilege policy differs')
    check(host['PidMode'] in ('', 'private') and host['IpcMode'] in ('', 'private'), 'target shares another namespace')
    check(host['NetworkMode'] == 'bridge' and sorted(info['NetworkSettings']['Networks']) == ['bridge'] and
          not host['PortBindings'] and not host['PublishAllPorts'], 'target network differs')
    mounts = info['Mounts']
    mount = mounts[0] if len(mounts) == 1 else {}
    check(mount.get('Type') == 'volume' and mount.get('Name') == VOLUME and mount.get('Driver') == 'local' and
          mount.get('Destination') == STATE and mount.get('RW') is True and host['Binds'] in (None, [VOLUME + ':' + STATE]),
          'unexpected target mounts')
    check(volume['Driver'] == 'local' and not volume['Options'] and (volume.get('Labels') or {}).get('hqr.task') == TASK_LABEL,
          'state volume identity/options differ')


def main(argv):
    extra = argparse.ArgumentParser(add_help=False)
    extra.add_argument('--advanced-manifest', required=True)
    extra.add_argument('--admission-only', action='store_true', help='inspect target policy and listeners, then exit before any target command')
    admission_args, remaining = extra.parse_known_args(argv)
    args = parse(remaining)
    run = S2Run(args.receipts)

    def admit():
        info = json.loads(run.docker('inspect', TARGET).stdout)[0]
        volume = json.loads(run.docker('volume', 'inspect', VOLUME).stdout)[0]
        validate_target(info, volume)
        return {'container': info['Id'], 'listeners': listener_admission()}
    admission = run.step('admission-before-any-mutation', admit)
    if admission_args.admission_only:
        return dict(admission, admission_only=True)
    # Recheck the exact target before every command/probe that could mutate it.
    for name in ('hermes', 'json'):
        original = getattr(run, name)
        def admitted(*args, _original=original, **kwargs):
            admit()
            return _original(*args, **kwargs)
        setattr(run, name, admitted)

    def callbacks():
        def off(_revision):
            a = single(run.probe('mode off'))
            b = single(run.probe('status'))
            require_off(a, b)
            return b
        def scan(revision):
            data = run.json(SCAN, revision, stdin=json.dumps(run.expected(revision)))
            check(data['bytes_match'] and data['scan_on_install'] is not False, 'scanner bytes or policy differ', data)
            require_safe_scan(data)
            return data
        def install(revision):
            done = run.hermes('plugins', 'install', ORIGIN, '--force', '--ref', revision, '--no-enable')
            check(inactive(run.hermes('plugins', 'show', PLUGIN).stdout), 'replacement enabled before explicit enable')
            return {'exit': done.returncode}
        def enable(revision):
            run.hermes('config', 'set', f'plugins.entries.{PLUGIN}.settings.deployment', deployment(revision))
            return {'exit': run.hermes('plugins', 'enable', PLUGIN).returncode}
        def smoke(revision):
            result = run.probe('status')
            installed_modules(result)
            state = single(result)
            check(state['mode_effective'] == 'off' and state['deployment']['revision'] == revision, 'smoke differs', state)
            return state
        return {'off': off, 'disable': lambda _r: {'exit': run.hermes('plugins', 'disable', PLUGIN).returncode},
                'scan': scan, 'install': install, 'files': lambda r: run.tree(r, GITHUB), 'enable': enable, 'smoke': smoke}

    run.advanced_manifest = json.loads(Path(admission_args.advanced_manifest).read_text(encoding='utf-8'))
    run.step('dependency-requires-effective-off', lambda: callbacks()['off'](args.candidate))
    run.step('pinned-advanced-delegation', lambda: install_advanced(run))
    run.step('candidate-swap', lambda: swap_revision(args.candidate, callbacks()))
    def qualify():
        result = run.json(COMPAT)
        check(result['ok'], 'Docker host fingerprint not qualified; stop before Auto', result)
        return result
    run.step('candidate-host-fingerprints', qualify)
    results = run.step('native-auto-scenarios', lambda: run.json(EXERCISE))
    def removal_refusal():
        try:
            product_remove(run)
        except Failure:
            status = single(run.probe('status'))
            check(status.get('mode_saved') == 'auto' or status.get('applied', {}).get('auto_declared'), 'removal refused for wrong reason')
            return {'pass': True, 'observed': 'product removal refused while Auto declared; native CLI is not intercepted'}
        raise Failure('product removal unexpectedly reached native remove')
    results['consumers']['scenarios']['E2'] = run.step('removal-refused-in-auto', removal_refusal)
    before_disable = run.json(READ_PROFILE)
    run.step('absence-disable-with-auto', lambda: {'exit': run.hermes('plugins', 'disable', PLUGIN).returncode})
    def disabled_proof():
        current = run.json(READ_PROFILE)
        check(absence_projection(current) == absence_projection(before_disable), 'disabled configuration changed outside native enable/disable lists')
        # HQR-32: Rich truncates long keys; the native plain view preserves exact plugin identity.
        listing = run.hermes('plugins', 'list', '--plain', '--no-bundled').stdout
        show = run.hermes('plugins', 'show', PLUGIN).stdout
        listed = any(fields and fields[-1] == PLUGIN for fields in (line.split() for line in listing.splitlines()))
        check(listed and inactive(show), 'native disabled diagnostic missing')
        return {'configuration_preserved': True, 'native_disabled_diagnostic': True}
    run.step('absence-config-and-native-diagnostic-while-disabled', disabled_proof)
    run.step('absence-reenable', lambda: {'exit': run.hermes('plugins', 'enable', PLUGIN).returncode})
    def absence():
        status = single(run.probe('status'))
        check(status.get('applied', {}).get('absence') is not None, 'absence marker not reported', status)
        return status['applied']
    run.step('absence-readback', absence)
    run.step('rollback-swap', lambda: swap_revision(args.rollback, callbacks()))
    run.step('rollback-observe-smoke', lambda: single(run.probe('mode observe')))
    run.step('candidate-return', lambda: swap_revision(args.candidate, callbacks()))
    run.step('final-observe', lambda: single(run.probe('mode observe')))
    def unresolved():
        results['consumers']['pending_consumer_proofs'] = [n for n in __import__('s3_native_consumers').REQUIRED
            if results['consumers']['scenarios'].get(n, {}).get('pass') is not True]
        try:
            require_complete(results['consumers'])
        except RuntimeError as exc:
            raise Failure(str(exc)) from exc
        return results
    run.step('acceptance-requires-all-native-consumers', unresolved)


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Failure as error:
        raise SystemExit(str(error))
