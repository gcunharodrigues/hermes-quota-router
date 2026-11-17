# Implements decisions/hqr-20-amendment.md, section 4, D6/D15 and AC-18/19/20/23; decisions/hqr-38-spec.md, D-29.
"""Durable best-effort Auto transactions and baseline restoration, serialized across local processes."""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import tempfile

from . import groups, storage


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable(path, value):
    """Atomically publish a private record without following symlinks."""
    path = Path(path)
    with storage.directory(path.parent) as fd:
        storage.publish(fd, path.name, value)


class Engine:
    def __init__(self, directory, backend, compatible, checkpoint=None):
        self.directory = Path(directory)
        self.backend = backend
        self.compatible = compatible
        self.checkpoint = checkpoint or (lambda _point: None)
        self.state = None
        self._directory_fd = None
        self.compatibility = {"ok": False, "reasons": ["not_checked"]}
        self.absence = None

    # decisions/hqr-20-amendment.md, section 4 and D6: serialize plugin writers, not external writers.
    @contextmanager
    def locked(self, *, legacy_migration=False):
        with storage.directory(self.directory, create=True) as fd:
            handle = storage.open_record(fd, 'auto.lock', os.O_RDWR | os.O_CREAT)
            fcntl.flock(handle, fcntl.LOCK_EX)
            self._directory_fd = fd
            try:
                candidate = self.read_record('state.json', {"schema": 1, "groups": {}, "history": [], "generation": 0,
                                                             "auto_declared": False, "last_cycle": None})
                self.validate_state(candidate)
                self.state = candidate
                # SOL-04: the explicit reconciler owns a pending migration; ordinary Auto/OFF must wait.
                if not legacy_migration:
                    from .downgrade import migration_pending
                    if migration_pending(fd):
                        raise ValueError('Pending legacy migration requires explicit reconciliation')
                yield
            finally:
                self._directory_fd = None
                fcntl.flock(handle, fcntl.LOCK_UN)
                os.close(handle)

    def read_record(self, name, default=None):
        if self._directory_fd is not None:
            return storage.read(self._directory_fd, name, deepcopy(default))
        try:
            with storage.directory(self.directory) as fd:
                return storage.read(fd, name, deepcopy(default))
        except FileNotFoundError:
            return deepcopy(default)

    def persist(self, name, value):
        if self._directory_fd is None:
            raise RuntimeError('Storage lock required')
        storage.publish(self._directory_fd, name, value)

    @staticmethod
    def validate_state(state):
        if not isinstance(state, dict) or state.get("schema") != 1 or not isinstance(state.get("groups"), dict):
            raise ValueError("Invalid Auto state")
        for role, entry in state["groups"].items():
            if not isinstance(entry, dict):
                raise ValueError("Invalid group state")
            for kind in ("baseline", "last"):
                if kind in entry:
                    groups.validate_projection(role, entry[kind])
        for record in state.get("history", []):
            groups.validate_projection(record["group"], record["values"])

    def save(self):
        self.persist('state.json', self.state)

    def clear_journal(self):
        try:
            os.unlink('journal.json', dir_fd=self._directory_fd)
        except FileNotFoundError:
            pass
        os.fsync(self._directory_fd)
        self.checkpoint('journal_deleted')

    def check_compat(self):
        try:
            self.compatibility = self.compatible()
        except Exception:
            self.compatibility = {"ok": False, "reasons": ["compatibility_unavailable"]}
        return self.compatibility.get('ok') is True

    def exclude(self, role, fields):
        entry = self.state['groups'].setdefault(role, {})
        entry.update(active=False, excluded=sorted(fields))
        self.save()

    # decisions/s3-plan.md, "Escopo": recheck qualification and group preconditions before every native write.
    def checked(self, role, route_projections=()):
        if not self.check_compat():
            return None
        # decisions/hqr-38-spec.md, D-29: a route's safety net depends on the same subagent backend as the route.
        if groups.owner(role) != 'conversation' and not self.compatibility.get('subagents', {'ok': True}).get('ok'):
            self.exclude(role, ['advanced_delegation_unavailable'])
            return None
        document = self.backend.read()
        errors = groups.preconditions(document, role, route_projections)
        if errors:
            self.exclude(role, errors)
            return None
        # README.md, HQR-27: native null deletes a key, so explicit-null baselines cannot be restored exactly.
        if getattr(self.backend, 'can_store_null', True) is False:
            nulls = [k for k, v in groups.project(document, role, route_projections).items() if v.get('present') and v.get('value') is None]
            if nulls:
                self.exclude(role, nulls)
                return None
        return document

    # decisions/hqr-20-amendment.md, AC-20: persist last-applied before deleting the durable intention.
    def commit(self, journal):
        role = journal['group']
        entry = self.state['groups'][role]
        entry['last'] = journal['target']
        if journal.get('restore'):
            entry.update(active=False, restored=True)
        else:
            self.state['generation'] += 1
            self.state['history'].append({"generation": self.state['generation'], "at": journal['at'], "group": role,
                                          "values": journal['target']})
            self.state['history'] = self.state['history'][-128:]
            entry.update(generation=self.state['generation'], applied_at=journal['at'])
        self.save()
        self.checkpoint('committed')
        self.clear_journal()

    def write(self, journal):
        role = journal['group']
        routes = (journal['prior'], journal['target'])
        document = self.checked(role, routes)
        if document is None:
            return False
        allowed = []
        if groups.is_fallback(role) and not journal.get('restore'):
            allowed = journal['target'][groups.FALLBACK].get('value') or []
            errors = groups.effective_fallback_errors(document, role, journal['target'], allowed)
            if errors:
                self.exclude(role, errors)
                return False
        self.backend.write(*groups.changes(document, role, journal['target']))
        self.checkpoint('written')
        reread = self.checked(role)
        if reread is None:
            return False
        if groups.is_fallback(role) and not journal.get('restore'):
            errors = groups.effective_fallback_errors(reread, role, journal['target'], allowed)
            if errors:
                self.exclude(role, errors)
                return False
        current = groups.project(reread, role)
        self.checkpoint('reread')
        if current != journal['target']:
            # Leave the intention for the same four-way reconciliation on the next cycle.
            return False
        self.commit(journal)
        return True

    def recover_locked(self):
        if not self.check_compat():
            return False
        journal = self.read_record('journal.json')
        if not journal:
            return True
        role = journal['group']
        groups.validate_projection(role, journal["prior"])
        groups.validate_projection(role, journal["target"])
        entry = self.state['groups'].get(role, {})
        if entry.get('excluded'):
            self.clear_journal()
            return True
        routes = (journal['prior'], journal['target'])
        document = self.checked(role, routes)
        if document is None:
            if self.state["groups"].get(role, {}).get("excluded"):
                self.clear_journal()
                return True
            return False
        current = groups.project(document, role, routes)
        prior, target = journal['prior'], journal['target']
        # decisions/hqr-20-amendment.md, D15/AC-19/20: prior discards, target commits, mixture completes, third value excludes.
        if current == prior:
            self.clear_journal()
        elif current == target:
            # A crash after last-applied was committed must not mint a second generation.
            if entry.get('last') == target and (journal.get('restore') or entry.get('applied_at') == journal['at']):
                self.clear_journal()
            else:
                self.commit(journal)
        else:
            third = [key for key in current if current[key] not in (prior[key], target[key])]
            if third:
                self.exclude(role, third)
                self.clear_journal()
                return True
            # decisions/hqr-20-amendment.md, D15: an exact human-created prior/target mixture is indistinguishable from a crash.
            return self.write(journal)
        return True

    def recover(self):
        with self.locked():
            return self.recover_locked()

    def transact(self, role, target, now, restore=False):
        if self.read_record('journal.json'):
            return False
        document = self.checked(role)
        if document is None:
            return
        entry = self.state['groups'].get(role)
        if entry and entry.get('excluded'):
            return
        current = groups.project(document, role)
        # decisions/hqr-20-amendment.md, section 4/AC-19: baseline belongs to enrollment, never to a later decision.
        if entry is None or entry.get('restored'):
            entry = {"baseline": current, "last": current, "active": True}
            self.state['groups'][role] = entry
            self.save()
            self.checkpoint('enrolled')
        # decisions/hqr-20-amendment.md, AC-19: any detected external edit excludes the whole group, including on OFF.
        if current != entry['last']:
            self.exclude(role, [k for k in current if current[k] != entry['last'][k]])
            return
        target = entry['baseline'] if restore else target
        if target == current:
            if restore:
                entry.update(active=False, restored=True)
                self.save()
            elif 'applied_at' not in entry:
                journal = {"group": role, "prior": current, "target": target, "at": now, "restore": False}
                self.persist('journal.json', journal)
                self.checkpoint('journal')
                self.commit(journal)
            return
        journal = {"group": role, "prior": current, "target": target, "at": now, "restore": restore}
        self.persist('journal.json', journal)
        self.checkpoint('journal')
        return self.write(journal)

    def cycle(self, selections, now, enabled=None):
        with self.locked():
            if not self.recover_locked():
                return
            enabled = set(selections) if enabled is None else set(enabled)
            for role, entry in list(self.state['groups'].items()):
                if role not in enabled and entry.get('active'):
                    if self.transact(role, None, now, restore=True) is False:
                        return False
            for role in sorted(enabled):
                entry = self.state["groups"].get(role)
                document = self.checked(role)
                if document is not None:
                    current = groups.project(document, role)
                    if entry is None or entry.get("restored"):
                        self.state["groups"][role] = {"baseline": current, "last": current, "active": True}
                        self.save()
                    elif entry.get('active') and current != entry['last']:
                        self.exclude(role, [key for key in current if current[key] != entry['last'][key]])
            for role, selection in selections.items():
                if role in enabled:
                    if groups.is_fallback(role) and selection.get('blocked_fields'):
                        self.exclude(role, selection['blocked_fields'])
                        continue
                    # decisions/hqr-38-spec.md, "Rede de segurança": an empty chain depends on the enrolled baseline.
                    baseline = (self.state['groups'].get(role) or {}).get('baseline')
                    target = groups.target(role, selection, baseline=baseline)
                    if groups.is_fallback(role):
                        document = self.checked(role)
                        if document is None:
                            continue
                        errors = groups.effective_fallback_errors(document, role, target, selection['chain'])
                        if errors:
                            self.exclude(role, errors)
                            continue
                    if self.transact(role, target, now) is False:
                        return False
            self.state.update(auto_declared=True, last_cycle=now)
            self.save()

    def needs_restoration(self):
        with self.locked():
            return bool(self.state.get('auto_declared') or self.read_record('journal.json') or
                        any(e.get('active') for e in self.state['groups'].values()))

    # decisions/hqr-20-amendment.md, section 4/AC-19: restore only intact groups and preserve absent keys.
    def restore(self, now):
        with self.locked():
            if not self.recover_locked():
                return False
            for role, entry in list(self.state['groups'].items()):
                if entry.get('active'):
                    if self.transact(role, None, now, restore=True) is False:
                        return False
            if self.read_record('journal.json') or any(e.get('active') for e in self.state['groups'].values()):
                return False
            self.state.update(auto_declared=False, last_cycle=now)
            self.save()
            return True

    def begin(self):
        with self.locked():
            if not self.recover_locked():
                return False
            if not self.state.get("auto_declared"):
                self.state["groups"] = {r: e for r, e in self.state["groups"].items() if e.get("active")}
                self.state["auto_declared"] = True
                self.save()
            return True

    def loaded(self, now):
        with self.locked():
            last = self.state.get('last_cycle')
            if self.state.get('auto_declared') and last is not None:
                self.absence = {"from": last, "to": now, "reason": "Auto declarado; plugin ausente ou sem ciclo"}
            return self.report(now)

    def report(self, now):
        try:
            state = self.state or self.read_record('state.json', {"schema": 1, "groups": {}, "history": [], "generation": 0})
            self.validate_state(state)
        except (ValueError, KeyError, TypeError):
            return {"generation": 0, "last_applied": None, "age_s": None, "groups_out": {},
                    "compatibility": {"ok": False, "reasons": ["invalid_auto_state"]}, "absence": self.absence}
        history = state.get('history', [])
        latest = history[-1] if history else None
        def view(entry):
            return {"values": entry['last'], "generation": entry.get('generation'),
                    "age_s": max(0, now - entry['applied_at']) if 'applied_at' in entry else None, "active": entry.get('active', False)}
        # decisions/hqr-38-spec.md, D-29: safety net groups are reported apart from the S3 route groups.
        return {"generation": state['generation'], "last_applied": latest,
                "groups": {role: view(entry) for role, entry in state['groups'].items() if 'last' in entry and not groups.is_fallback(role)},
                "safety_net": {role: view(entry) for role, entry in state['groups'].items() if 'last' in entry and groups.is_fallback(role)},
                "age_s": max(0, now - latest['at']) if latest else None,
                "groups_out": {r: e['excluded'] for r, e in state['groups'].items() if e.get('excluded')},
                "compatibility": self.compatibility, "absence": self.absence, "last_cycle": state.get('last_cycle'),
                "auto_declared": state.get('auto_declared', False),
                "limit": "Escritor único; edição entre comparação e escrita pode ser perdida; mistura exata anterior/alvo é completada"}



# decisions/s3-plan.md, R2: use native Changes, never credential-bearing model-switch resolution.
class NativeBackend:
    """Native Changes only; no model switch or credential-bearing resolution."""
    can_store_null = False

    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        from hermes_cli.config_backend import read_config_doc
        return read_config_doc(self.path)

    def write(self, updates, unset):
        from hermes_cli.config_backend import Changes, write_changes
        write_changes(self.path, Changes(document=None, set=updates, unset=tuple(unset), extra_content_on_create=None))
