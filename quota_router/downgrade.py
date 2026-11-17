# Implements SOL-04 from the independent HQR-38 review; see decisions/hqr-38-delivery.md.
"""Lossless downgrade preparation and explicit, locked publication; never automatic migration.

The returned record is NOT proof of OFF or a safe persisted swap. An operator must first qualify and authorize
that separate procedure, including locking, backup, compare-before-publish, readback and interruption recovery.
The archive is inert historical evidence, never a source for automatic enrollment or config restoration.
"""
from copy import deepcopy
import hashlib
import json
import os

from . import groups, storage
from .apply import Engine

ROLLBACK = '233f4beae8fa0e089f95a8c6ef3cee1ba0b7ff8a'
ARCHIVE = 'hqr38_downgrade_archive'
MIGRATION = 'hqr38-downgrade.json'
MAX_RECORD = 1024 * 1024


def prepare_legacy_state(state, *, mode, journal):
    """Project an already confirmed OFF snapshot into the old validator's language, preserving its full history.

    The old validator ignores the namespaced archive and all old Engine saves retain unknown top-level fields.
    Return a separate value; never modify the supplied state or any configuration. Decline nested archives.
    """
    Engine.validate_state(state)
    if mode != 'off' or state.get('auto_declared') is not False or journal is not None or ARCHIVE in state:
        raise ValueError('Confirmed OFF without pending journal or previous archive required')
    for entry in state['groups'].values():
        if entry.get('active') is not False:
            raise ValueError('Active or unqualified group')
        if not entry.get('excluded') and (entry.get('restored') is not True or entry.get('last') != entry.get('baseline')):
            raise ValueError('Restoration incomplete')
    result = deepcopy(state)
    result['groups'] = {role: entry for role, entry in result['groups'].items() if not groups.is_fallback(role)}
    result['history'] = [record for record in result.get('history', []) if not groups.is_fallback(record['group'])]
    result[ARCHIVE] = {'rollback': ROLLBACK, 'purpose': 'history_only_no_restore', 'source_state': deepcopy(state)}
    return result


def _encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True).encode('utf-8')


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate migration key')
            result[key] = value
        return result
    def constant(_value):
        raise ValueError('Non-finite migration value')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=constant)


def _snapshot(fd, name):
    handle = storage.open_record(fd, name)
    with os.fdopen(handle, 'rb') as stream:
        info = os.fstat(stream.fileno())
        raw = stream.read(MAX_RECORD + 1)
    if len(raw) > MAX_RECORD:
        raise ValueError('Migration record too large')
    return raw, (info.st_dev, info.st_ino)


def _intent(fd):
    try:
        raw, _identity = _snapshot(fd, MIGRATION)
    except FileNotFoundError:
        return None
    value = _decode(raw)
    keys = {'schema', 'purpose', 'phase', 'source_sha256', 'target_sha256', 'config_sha256', 'backup'}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError('Malformed migration receipt')
    if value['schema'] != 1 or value['purpose'] != 'hqr38_legacy_downgrade' or value['phase'] not in ('pending', 'complete'):
        raise ValueError('Unsupported migration receipt')
    for key in ('source_sha256', 'target_sha256', 'config_sha256'):
        digest = value[key]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Invalid migration fingerprint')
    if value['backup'] != 'hqr38-rollback-' + value['source_sha256'] + '.json':
        raise ValueError('Invalid migration backup name')
    return value


def migration_pending(fd):
    """SOL-04: a complete receipt is a durable gate, not permission to restore archived configuration."""
    intent = _intent(fd)
    if intent is None:
        return False
    if intent['phase'] == 'pending':
        return True
    original, _identity = _snapshot(fd, intent['backup'])
    prepared = prepare_legacy_state(_decode(original), mode='off', journal=None)
    current, _identity = _snapshot(fd, 'state.json')
    if (_digest(original) != intent['source_sha256'] or _digest(_encode(prepared)) != intent['target_sha256']
            or _decode(current).get(ARCHIVE) != prepared[ARCHIVE]):
        raise ValueError('Unverified completed migration')
    # A receipt rename may have succeeded before an earlier directory fsync failed.
    os.fsync(fd)
    return False


def _context(engine, fd, mode_reader, roles):
    if mode_reader() != 'off' or not engine.check_compat():
        raise ValueError('Qualified OFF required for migration')
    try:
        os.stat('journal.json', dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        raise ValueError('Pending Auto journal')
    with storage.directory(engine.directory) as current:
        left, right = os.fstat(fd), os.fstat(current)
        if (left.st_dev, left.st_ino) != (right.st_dev, right.st_ino):
            raise ValueError('Migration directory changed')
    document = engine.backend.read()
    projection = {role: groups.project(document, role) for role in roles}
    return _digest(_encode(projection))


def _backup(fd, name, expected, *, create):
    if create:
        try:
            handle = storage.open_record(fd, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            pass
        else:
            # A failed/incomplete exclusive backup is retained and refused on the next attempt.
            with os.fdopen(handle, 'wb') as stream:
                stream.write(expected)
                stream.flush()
                os.fsync(stream.fileno())
    actual, _identity = _snapshot(fd, name)
    if actual != expected:
        raise ValueError('Migration backup differs')
    handle = storage.open_record(fd, name)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)
    os.fsync(fd)


def publish_legacy_state(engine, expected, *, mode_reader, checkpoint=None):
    """SOL-04 explicit operator action; reconcile successfully before loading the pinned legacy Engine.

    The caller supplies the original bytes, never a fresh baseline on recovery.
    Only cooperative writers share this lock; comparisons do not provide CAS against external writers.
    No configuration, credentials, provider or installation is changed by this operation.
    """
    if not isinstance(expected, bytes) or not expected or len(expected) > MAX_RECORD:
        raise ValueError('Bounded original snapshot bytes required')
    original = _decode(expected)
    prepared = prepare_legacy_state(original, mode='off', journal=None)
    target = _encode(prepared)
    if len(target) > MAX_RECORD:
        raise ValueError('Prepared migration record too large')
    checkpoint = checkpoint or (lambda _point: None)
    roles = sorted(set(original['groups']) | {'conversation'})
    source_hash, target_hash = _digest(expected), _digest(target)
    backup = 'hqr38-rollback-' + source_hash + '.json'
    with engine.locked(legacy_migration=True):
        fd = engine._directory_fd
        current, identity = _snapshot(fd, 'state.json')
        intent = _intent(fd)
        config_hash = _context(engine, fd, mode_reader, roles)
        if current not in (expected, target):
            raise ValueError('Migration snapshot conflict')
        if intent is None:
            if current != expected:
                raise ValueError('Prepared state without migration receipt')
            _backup(fd, backup, expected, create=True)
            checkpoint('backup_ready')
            if _context(engine, fd, mode_reader, roles) != config_hash:
                raise ValueError('Configuration changed before migration intention')
            intent = {'schema': 1, 'purpose': 'hqr38_legacy_downgrade', 'phase': 'pending',
                      'source_sha256': source_hash, 'target_sha256': target_hash, 'config_sha256': config_hash, 'backup': backup}
            storage.publish(fd, MIGRATION, intent)
        else:
            if (intent['source_sha256'], intent['target_sha256'], intent['config_sha256']) != (source_hash, target_hash, config_hash):
                raise ValueError('Migration intention conflict')
            _backup(fd, backup, expected, create=False)
        if intent['phase'] == 'complete':
            if current != target:
                raise ValueError('Completed migration state changed')
            os.fsync(fd)
            return {'status': 'complete', 'backup': backup}
        checkpoint('intent_ready')
        if current == expected:
            checkpoint('before_publish')
            if _context(engine, fd, mode_reader, roles) != intent['config_sha256']:
                raise ValueError('Configuration changed before publication')
            fresh, fresh_identity = _snapshot(fd, 'state.json')
            if fresh != expected or fresh_identity != identity:
                raise ValueError('Migration publication target changed')
            storage.publish(fd, 'state.json', prepared)
        checkpoint('published')
        reread, _identity = _snapshot(fd, 'state.json')
        if reread != target:
            raise ValueError('Migration readback differs')
        checkpoint('verified')
        if _context(engine, fd, mode_reader, roles) != intent['config_sha256']:
            raise ValueError('Configuration changed before completion')
        final, _identity = _snapshot(fd, 'state.json')
        if final != target:
            raise ValueError('Migration state changed before completion')
        engine.state = deepcopy(prepared)
        storage.publish(fd, MIGRATION, dict(intent, phase='complete'))
        os.fsync(fd)
        checkpoint('completed')
        return {'status': 'complete', 'backup': backup}
