#!/usr/bin/env python3
"""D-43 S1 exercise; run only in the admitted offline Hermes container."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from types import MethodType
from typing import Any


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def exercise(command, read, resolve, collect):
    """Check the same transitions through a supplied command dispatcher and config backend."""
    command('mode observe')
    command('config approve-map base')
    baseline = read()
    collect('exhausted')
    observed = command('explain')
    require(observed['decisions']['conversation']['choice'] == 'anthropic', 'Observe did not select the eligible alternate')
    require(read() == baseline, 'Observe changed the configuration')
    collect('seed')
    command('mode auto')
    initial = read()
    require(resolve(initial)['provider'] == 'openai-codex', 'seed did not retain Codex')
    collect('timeout')
    timeout = command('apply')
    require(timeout['quota']['providers']['openai-codex'].get('last_known') is True, 'timeout did not carry reading')
    require(read() == initial, 'timeout changed the configuration')
    collect('malformed')
    unknown = command('apply')
    require(unknown['decisions']['conversation']['reason'] == 'incumbent_reading_unknown', 'malformed reading was not unknown')
    require(resolve(read()) == resolve(initial), 'malformed reading changed the primary route')
    collect('exhausted')
    applied = command('apply')
    selected = applied['decisions']['conversation']['choice']
    resolved = resolve(read())
    require(selected == 'anthropic' and resolved['provider'] == selected, 'confirmed exhaustion did not switch natively')
    return {'observe_no_write': True, 'timeout_retained': True, 'malformed_retained': True,
            'confirmed_exhaustion': resolved, 'generation': applied['applied']['generation']}


def admitted_home():
    require(os.getuid() == 10001 and Path('/.dockerenv').is_file(), 'not the dedicated unprivileged container')
    require(os.environ.get('HOME') == '/home/hqr', 'unexpected HOME')
    require(set(p.name for p in Path('/sys/class/net').iterdir()) == {'lo'}, 'test requires an offline namespace')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    require(status.get('NoNewPrivs', '').strip() == '1' and int(status['CapEff'], 16) == 0, 'container security flags differ')
    require(not Path('/var/run/docker.sock').exists(), 'Docker socket is accessible inside the target')
    require(not any(name.endswith(('_API_KEY', '_TOKEN', '_SECRET', '_PASSWORD')) for name in os.environ),
            'credential-like environment variable present')
    home = Path(os.environ['HERMES_HOME']).resolve(strict=True)
    require(home.parent == Path('/home/hqr') and re.fullmatch(r'd43-[a-zA-Z0-9_-]+', home.name), 'require a new D-43 test home')
    require(not any((home / name).exists() for name in ('.env', 'auth.json', 'profiles')), 'test home is not synthetic')
    return home


def verify_install(home, manifest, revision):
    data = json.loads(manifest.read_text())
    require(data['revision'] == revision, 'manifest does not describe the selected revision')
    root = home / 'plugins' / 'hermes-quota-router'
    require(root.is_dir() and not root.is_symlink() and root.resolve() == root, 'plugin path is not inside the test home')
    files = {}
    for path in root.rglob('*'):
        sub = path.relative_to(root)
        if sub.parts[0] == '.git':
            continue
        require(not path.is_symlink() and (path.is_file() or path.is_dir()), 'non-ordinary path in installed plugin')
        if path.is_file():
            require(not re.search(r'(^|/)(\.env(?:\.[^/]+)?|auth\.json|credentials\.json)$', sub.as_posix()), 'credential-like path in installed plugin')
            require(sub.as_posix() in data['files'], 'unexpected installed file')
            files[sub.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    require(files and files == data['files'], 'installed bytes differ from candidate manifest')


def native_exercise(home):
    from datetime import datetime, timedelta, timezone
    import importlib
    from types import SimpleNamespace
    from s3_native_consumers import NativeHost, ProbeGuard

    guard = ProbeGuard(home, missing_credentials=True)
    os.open = guard.wrap_open(os.open)
    sys.addaudithook(guard.audit)
    os.environ.update(HERMES_DISABLE_LAZY_INSTALLS='1', GIT_NO_LAZY_FETCH='1',
                      GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    native = NativeHost()
    guard.missing_roots.add(native.root)
    guard.readonly_commands.add((('git', 'rev-parse', 'HEAD'), str(native.root)))
    from hermes_cli.config import get_config_path
    from hermes_cli.config_backend import Changes, read_config_doc, write_changes
    from hermes_cli.plugins import get_plugin_command_handler

    handler = get_plugin_command_handler('quota-router')
    if not isinstance(handler, MethodType):
        raise RuntimeError('installed plugin did not register its native command')
    manager: Any = handler.__self__
    require(Path(handler.__func__.__code__.co_filename).resolve().is_relative_to(home / 'plugins' / 'hermes-quota-router'),
            'native command did not load from the verified plugin tree')
    require(manager.compatible()['ok'], 'installed Hermes is not qualified')
    path = get_config_path()
    require(Path(path).resolve() == home / 'config.yaml', 'native configuration resolved outside the test home')
    readings = importlib.import_module(manager.__module__.rsplit('.', 1)[0] + '.readings')
    routes = importlib.import_module(manager.__module__.rsplit('.', 1)[0] + '.routes')
    defaults = routes.defaults('openai-codex')
    write_changes(path, Changes(set={'model.default': 'gpt-6.1-sol', 'model.provider': 'openai-codex',
                                    'model.base_url': defaults['base_url'], 'model.api_mode': defaults['api_mode'],
                                    'agent.reasoning_effort': 'low'}))
    now = datetime.now(timezone.utc)
    manager.clock = lambda: now

    def command(text):
        result = json.loads(handler(text + ' --json'))
        require(result['ok'], 'native plugin command failed: ' + text)
        return result

    def collect(case):
        def reader(provider):
            is_codex = provider == 'openai-codex'
            if is_codex and case == 'timeout':
                return readings._NativeFailure({'kind': 'timeout'})
            used = (100 if case == 'exhausted' else 60) if is_codex else (80 if case == 'seed' else 10)
            window = SimpleNamespace(label='Weekly' if is_codex else 'Current week',
                                     used_percent=used, reset_at=now + timedelta(hours=72), scope='account')
            limit = {'primary_window': {'limit_window_seconds': 604800}, 'allowed': used < 100,
                     'limit_reached': used >= 100}
            if is_codex and case == 'malformed':
                limit['tertiary_window'] = {'used_tokens': 10}
            return SimpleNamespace(provider=provider, source='usage_api' if is_codex else 'oauth_usage_api',
                                   fetched_at=now, windows=(window,), unavailable_reason=None,
                                   raw={'rate_limit': limit} if is_codex else None)
        manager.importer = lambda: reader
        manager.cache.clear()

    try:
        command('config set credits.openai-codex false')
        return exercise(command, lambda: read_config_doc(path), native.route, collect)
    finally:
        command('mode off')
        manager.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slice', choices=['s1'], required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    require(re.fullmatch(r'[0-9a-f]{40}', args.candidate), 'candidate must be a full lowercase Git commit')
    home = admitted_home()
    receipt = args.receipt.resolve()
    require(receipt.parent == home, 'receipt must be inside the synthetic test home')
    verify_install(home, args.manifest, args.candidate)
    with receipt.open('x') as output:
        record = {'candidate': args.candidate, 'slice': args.slice, 'pass': False}
        try:
            record.update(checks=native_exercise(home), **{'pass': True})
        finally:
            json.dump(record, output, indent=2)
            output.write('\n')


if __name__ == '__main__':
    main()
