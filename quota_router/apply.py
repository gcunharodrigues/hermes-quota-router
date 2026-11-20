# Implements decisions/hqr-20-amendment.md, section 4, D6/D15 and AC-18/19/20/23; decisions/hqr-38-spec.md, D-29.
"""Durable best-effort Auto transactions and baseline restoration, serialized across local processes."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import fcntl
import os
from pathlib import Path
import threading
import time

from . import groups, storage

# Incidente 19/11: a slash command waits for auto.lock (thread and file) only until this time.monotonic() deadline;
# None waits as before. Worker waits use a separate nonblocking path so contention cannot leave waiter threads behind.
LOCK_DEADLINE: ContextVar[float | None] = ContextVar('quota_router_lock_deadline', default=None)
WORKER_TRY_LOCK = ContextVar('quota_router_worker_try_lock', default=False)
# Set by a read-only command: seconds it waits for a stale quota fetch; None fetches in the caller's thread as before.
FETCH_WAIT = ContextVar('quota_router_fetch_wait', default=None)


def lock_wait_s():
    deadline = LOCK_DEADLINE.get()
    return None if deadline is None else max(0.0, deadline - time.monotonic())


class LockBusy(TimeoutError):
    """Revisão S1, F6: auto.lock stayed busy past LOCK_DEADLINE; only this answers busy, never a network timeout."""


class LockAbandoned(LockBusy):
    """auto.lock stayed busy past LOCK_DEADLINE; the waiting helper thread now owns (and will close) the handle."""


def _flock(handle):
    deadline = LOCK_DEADLINE.get()
    if deadline is None:
        fcntl.flock(handle, fcntl.LOCK_EX)
        return
    if WORKER_TRY_LOCK.get():
        contended = False
        while True:
            if contended and time.monotonic() >= deadline:
                raise LockBusy('auto.lock busy')
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                contended = True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise LockBusy('auto.lock busy') from None
                time.sleep(min(0.025, remaining))
            else:
                if contended and time.monotonic() >= deadline:
                    fcntl.flock(handle, fcntl.LOCK_UN)
                    raise LockBusy('auto.lock busy')
                return
    # The same blocking LOCK_EX as above, waited for in a helper thread so the caller can give up at the deadline;
    # a lock obtained after that is released at once, and the helper closes the handle.
    outcome, settled, guard = {}, threading.Event(), threading.Lock()

    def wait():
        try:
            fcntl.flock(handle, fcntl.LOCK_EX)
        except BaseException as error:
            outcome['error'] = error
        with guard:
            if not outcome.get('abandoned'):
                settled.set()
                return
        try:
            if 'error' not in outcome:
                fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            os.close(handle)
    threading.Thread(target=wait, name='quota-router-lock', daemon=True).start()
    settled.wait(max(0.0, deadline - time.monotonic()))
    with guard:
        if not settled.is_set():
            outcome['abandoned'] = True
            raise LockAbandoned('auto.lock busy')
    if 'error' in outcome:
        raise outcome['error']


def durable(path, value):
    """Atomically publish a private record without following symlinks."""
    path = Path(path)
    with storage.directory(path.parent) as fd:
        storage.publish(fd, path.name, value)


class Engine:
    # decisions/aux-plan.md, AUXP-04: separate durable records and validators, with the same main defaults.
    def __init__(self, directory, backend, compatible, checkpoint=None, *, state_name='state.json', journal_name='journal.json', kind='main', snapshot=None):
        if kind not in ('main', 'auxiliary'):
            raise ValueError('Invalid engine kind')
        for name in (state_name, journal_name):
            if (not isinstance(name, str) or Path(name).name != name or not name.endswith('.json') or name.startswith('.')
                    or name == 'hqr38-downgrade.json' or name.startswith('hqr38-rollback-')):
                raise ValueError('Invalid engine record name')
        if state_name == journal_name or (kind == 'auxiliary' and {state_name, journal_name} & {'state.json', 'journal.json'}):
            raise ValueError('Engine records must be separate')
        from . import auxiliary
        self.kind = kind
        self.state_name, self.journal_name = state_name, journal_name
        self.projections = auxiliary if kind == 'auxiliary' else groups
        self.directory = Path(directory)
        self.backend = backend
        self.compatible = compatible
        self.checkpoint = checkpoint or (lambda _point: None)
        self.snapshot = snapshot
        self.state = None
        self._directory_fd = None
        # Correção 2026-11-18: the hook worker records events under this lock in its own thread; another thread waits
        # for it (bounded by LOCK_DEADLINE) instead of failing, and only the holding thread is refused a second lock.
        self._threads = threading.Lock()
        self._holder = None
        self.compatibility = {"ok": False, "reasons": ["not_checked"]}
        self.absence = None

    # decisions/hqr-20-amendment.md, section 4 and D6: serialize plugin writers, not external writers.
    @contextmanager
    def locked(self, *, legacy_migration=False):
        if self.kind != 'main' or self._holder == threading.get_ident():
            raise RuntimeError('Use one main lock, or locked_pair for auxiliary operations')
        timeout = lock_wait_s()
        if not self._threads.acquire(timeout=-1 if timeout is None else timeout):
            raise LockBusy('auto.lock busy')
        self._holder = threading.get_ident()
        try:
            with self._locked_file(legacy_migration):
                yield
        finally:
            self._holder = None
            self._threads.release()

    @contextmanager
    def _locked_file(self, legacy_migration):
        if self._directory_fd is not None:
            raise RuntimeError('Use one main lock, or locked_pair for auxiliary operations')
        with storage.directory(self.directory, create=True) as fd:
            handle = storage.open_record(fd, 'auto.lock', os.O_RDWR | os.O_CREAT)
            try:
                _flock(handle)
            except LockAbandoned:
                raise
            except BaseException:
                os.close(handle)
                raise
            self._directory_fd = fd
            try:
                self.load_state_locked()
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

    # Revisão da simplificação, F6: the lock's descriptor serves only the thread holding auto.lock; any other thread is
    # not locked, so it reads through its own descriptor and cannot persist.
    def _held_fd(self):
        return self._directory_fd if self._holder == threading.get_ident() else None

    def read_record(self, name, default=None):
        fd = self._held_fd()
        if fd is not None:
            return storage.read(fd, name, deepcopy(default))
        try:
            with storage.directory(self.directory) as fd:
                return storage.read(fd, name, deepcopy(default))
        except FileNotFoundError:
            return deepcopy(default)

    def persist(self, name, value):
        self.require_locked()
        storage.publish(self._directory_fd, name, value)

    def require_locked(self):
        if self._held_fd() is None:
            raise RuntimeError('Storage lock required')

    def load_state_locked(self):
        self.require_locked()
        candidate = self.read_record(self.state_name, {"schema": 1, "groups": {}, "history": [], "generation": 0,
                                                      "auto_declared": False, "last_cycle": None})
        self.validate_state(candidate, self.kind)
        self.state = candidate

    @staticmethod
    def validate_state(state, engine_kind='main'):
        from . import auxiliary
        projection_module = auxiliary if engine_kind == 'auxiliary' else groups
        if not isinstance(state, dict) or state.get("schema") != 1 or not isinstance(state.get("groups"), dict):
            raise ValueError("Invalid Auto state")
        for role, entry in state["groups"].items():
            if not isinstance(entry, dict):
                raise ValueError("Invalid group state")
            if engine_kind == 'auxiliary':
                auxiliary.task_name(role)
            elif not isinstance(role, str) or role.startswith('aux:'):
                raise ValueError('Invalid main group')
            for kind in ("baseline", "last"):
                if kind in entry:
                    projection_module.validate_projection(role, entry[kind])
        for record in state.get("history", []):
            projection_module.validate_projection(record["group"], record["values"])

    def save(self):
        self.persist(self.state_name, self.state)

    def clear_journal(self):
        self.require_locked()
        try:
            os.unlink(self.journal_name, dir_fd=self._directory_fd)
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
        if self.kind == 'auxiliary':
            prefix = 'auxiliary.' + self.projections.task_name(role) + '.'
            fields = [prefix + field if field in groups.FIELDS else field for field in fields]
        entry = self.state['groups'].setdefault(role, {})
        entry.update(active=False, excluded=sorted(fields))
        self.save()

    # decisions/s3-plan.md, "Escopo": recheck qualification and group preconditions before every native write.
    def checked(self, role, route_projections=()):
        if not self.check_compat():
            return None
        # decisions/hqr-38-spec.md, D-29: a route's safety net depends on the same subagent backend as the route.
        if self.kind == 'main' and groups.owner(role) != 'conversation' and not self.compatibility.get('subagents', {'ok': True}).get('ok'):
            self.exclude(role, ['advanced_delegation_unavailable'])
            return None
        document = self.backend.read()
        errors = self.projections.preconditions(document, role, route_projections)
        if errors:
            self.exclude(role, errors)
            return None
        # README.md, HQR-27: native null deletes a key, so explicit-null baselines cannot be restored exactly.
        if getattr(self.backend, 'can_store_null', True) is False:
            nulls = [k for k, v in self.projections.project(document, role, route_projections).items() if v.get('present') and v.get('value') is None]
            if nulls:
                self.exclude(role, nulls)
                return None
        return document

    # decisions/hqr-20-amendment.md, AC-20: persist last-applied before deleting the durable intention.
    def commit(self, journal, *, write_confirmed=False):
        role = journal['group']
        entry = self.state['groups'][role]
        entry['last'] = journal['target']
        if groups.is_fallback(role):
            # Only the write/readback path proves provenance. A no-op or recovery by equality does not.
            if write_confirmed and not journal.get('restore') and journal['prior'] != journal['target']:
                entry['fallback_written'] = True
            else:
                entry.pop('fallback_written', None)
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
        prior = None
        if groups.is_fallback(role) and not journal.get('restore'):
            allowed = journal['target'][groups.FALLBACK].get('value') or []
            entries = (self.state or {}).get('groups')
            entry = entries.get(role, {}) if isinstance(entries, dict) else {}
            prior = journal['prior'] if entry.get('active') and entry.get('fallback_written') is True and entry.get('last') == journal['prior'] else None
            if not allowed and journal['prior'][groups.FALLBACK].get('value') and prior is None:
                self.exclude(role, [groups.FALLBACK])
                return False
            errors = groups.effective_fallback_errors(document, role, journal['target'], allowed, prior=prior)
            if errors:
                self.exclude(role, errors)
                return False
        self.backend.write(*self.projections.changes(document, role, journal['target']))
        self.checkpoint('written')
        reread = self.checked(role)
        if reread is None:
            return False
        if groups.is_fallback(role) and not journal.get('restore'):
            errors = groups.effective_fallback_errors(reread, role, journal['target'], allowed, prior=prior)
            if errors:
                self.exclude(role, errors)
                return False
        current = self.projections.project(reread, role)
        self.checkpoint('reread')
        if current != journal['target']:
            # Leave the intention for the same four-way reconciliation on the next cycle.
            return False
        self.commit(journal, write_confirmed=True)
        return True

    def recover_locked(self):
        self.require_locked()
        if not self.check_compat():
            return False
        journal = self.read_record(self.journal_name)
        if not journal:
            return True
        role = journal['group']
        self.projections.validate_projection(role, journal["prior"])
        self.projections.validate_projection(role, journal["target"])
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
        current = self.projections.project(document, role, routes)
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
        self.require_locked()
        if self.read_record(self.journal_name):
            return False
        document = self.checked(role)
        if document is None:
            # decisions/aux-plan.md, AUXP-03/04: qualification loss suspends the caller, not just this group.
            return False if self.compatibility.get('ok') is not True else None
        entry = self.state['groups'].get(role)
        if entry and entry.get('excluded'):
            return
        current = self.projections.project(document, role)
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
        if restore and groups.is_fallback(role) and target != current and entry.get('fallback_written') is not True:
            # Recovery by equality can record a manual target. Do not revert a write we cannot attribute.
            self.exclude(role, [groups.FALLBACK])
            return
        if target == current:
            if restore:
                entry.update(active=False, restored=True)
                self.save()
            elif 'applied_at' not in entry:
                journal = {"group": role, "prior": current, "target": target, "at": now, "restore": False}
                self.persist(self.journal_name, journal)
                self.checkpoint('journal')
                self.commit(journal)
            return
        journal = {"group": role, "prior": current, "target": target, "at": now, "restore": restore}
        self.persist(self.journal_name, journal)
        self.checkpoint('journal')
        return self.write(journal)

    def cycle(self, selections, now, enabled=None):
        with self.locked():
            return self.cycle_locked(selections, now, enabled)

    def cycle_locked(self, selections, now, enabled=None):
        self.require_locked()
        if not self.recover_locked():
            return False
        enabled = set(selections) if enabled is None else set(enabled)
        for role, entry in list(self.state['groups'].items()):
            if role not in enabled and entry.get('active'):
                if self.transact(role, None, now, restore=True) is False:
                    return False
        for role in sorted(enabled):
            entry = self.state["groups"].get(role)
            document = self.checked(role)
            # AUXP-03/04: without qualification there is no new baseline and no completed cycle to publish.
            if document is None and self.compatibility.get('ok') is not True:
                return False
            if document is not None:
                current = self.projections.project(document, role)
                if entry is None or entry.get("restored"):
                    self.state["groups"][role] = {"baseline": current, "last": current, "active": True}
                    self.save()
                elif entry.get('active') and current != entry['last']:
                    self.exclude(role, [key for key in current if current[key] != entry['last'][key]])
        for role, selection in selections.items():
            if role in enabled:
                # AUXP-03: a structurally refused auxiliary has no baseline from which to build a target.
                if self.kind == 'auxiliary' and (self.state['groups'].get(role) or {}).get('excluded'):
                    continue
                if groups.is_fallback(role) and selection.get('blocked_fields'):
                    self.exclude(role, selection['blocked_fields'])
                    continue
                # decisions/hqr-38-spec.md, "Rede de segurança": an empty chain depends on the enrolled baseline.
                baseline = (self.state['groups'].get(role) or {}).get('baseline')
                target = self.projections.target(role, selection, baseline=baseline)
                if groups.is_fallback(role):
                    document = self.checked(role)
                    if document is None:
                        if self.compatibility.get('ok') is not True:
                            return False
                        continue
                    entries = (self.state or {}).get('groups')
                    entry = entries.get(role, {}) if isinstance(entries, dict) else {}
                    current = self.projections.project(document, role)
                    prior = current if entry.get('active') and entry.get('fallback_written') is True and entry.get('last') == current else None
                    if not selection['chain'] and current[groups.FALLBACK].get('value') and prior is None:
                        continue
                    errors = groups.effective_fallback_errors(document, role, target, selection['chain'], prior=prior)
                    if errors:
                        self.exclude(role, errors)
                        continue
                if self.transact(role, target, now) is False:
                    return False
                # Revisão da simplificação, F2: keep the tier that chose the applied route; only a subscription route
                # seeds the hysteresis after a restart, and a route without a recorded tier never does.
                entry = self.state['groups'].get(role) or {}
                if entry.get('active') and entry.get('last') == target and selection.get('tier'):
                    entry['tier'] = selection['tier']
                else:
                    entry.pop('tier', None)
        self.state.update(auto_declared=True, last_cycle=now)
        self.save()

    def needs_restoration(self):
        with self.locked():
            return self.needs_restoration_locked()

    def needs_restoration_locked(self):
        self.require_locked()
        return bool(self.state.get('auto_declared') or self.read_record(self.journal_name) or
                    any(e.get('active') for e in self.state['groups'].values()))


    # decisions/hqr-20-amendment.md, section 4/AC-19: restore only intact groups and preserve absent keys.
    def restore(self, now):
        with self.locked():
            return self.restore_locked(now)

    def restore_locked(self, now):
        self.require_locked()
        if not self.recover_locked():
            return False
        for role, entry in list(self.state['groups'].items()):
            if entry.get('active'):
                if self.transact(role, None, now, restore=True) is False:
                    return False
        if self.read_record(self.journal_name) or any(e.get('active') for e in self.state['groups'].values()):
            return False
        self.state.update(auto_declared=False, last_cycle=now)
        self.save()
        return True

    def begin(self):
        with self.locked():
            return self.begin_locked()

    def begin_locked(self):
        self.require_locked()
        if not self.recover_locked():
            return False
        if not self.state.get("auto_declared"):
            self.state["groups"] = {r: e for r, e in self.state["groups"].items() if e.get("active")}
            self.state["auto_declared"] = True
            self.save()
        return True

    def loaded(self, now):
        with self.locked():
            return self.loaded_locked(now)

    def loaded_locked(self, now):
        self.require_locked()
        last = self.state.get('last_cycle')
        if self.state.get('auto_declared') and last is not None:
            self.absence = {"from": last, "to": now, "reason": "Auto declarado; plugin ausente ou sem ciclo"}
        return self.report(now)

    def report(self, now):
        try:
            state = self.state or self.read_record(self.state_name, {"schema": 1, "groups": {}, "history": [], "generation": 0})
            self.validate_state(state, self.kind)
        except (ValueError, KeyError, TypeError):
            return {"generation": 0, "last_applied": None, "age_s": None, "groups_out": {},
                    "compatibility": {"ok": False, "reasons": ["invalid_auto_state"]}, "absence": self.absence}
        history = state.get('history', [])
        latest = history[-1] if history else None
        entries = (state or {}).get('groups')
        entries = entries if isinstance(entries, dict) else {}
        def view(entry):
            return {"values": entry['last'], "generation": entry.get('generation'), "tier": entry.get('tier'),
                    "age_s": max(0, now - entry['applied_at']) if 'applied_at' in entry else None, "active": entry.get('active', False)}
        # decisions/hqr-38-spec.md, D-29: safety net groups are reported apart from the S3 route groups.
        return {"generation": state['generation'], "last_applied": latest,
                "groups": {role: view(entry) for role, entry in entries.items() if 'last' in entry and not groups.is_fallback(role)},
                "safety_net": {role: dict(view(entry), fallback_written=entry.get('fallback_written') is True)
                               for role, entry in entries.items() if 'last' in entry and groups.is_fallback(role)},
                "age_s": max(0, now - latest['at']) if latest else None,
                "groups_out": {r: e['excluded'] for r, e in state['groups'].items() if e.get('excluded')},
                "compatibility": self.compatibility, "absence": self.absence, "last_cycle": state.get('last_cycle'),
                "auto_declared": state.get('auto_declared', False),
                "limit": "Escritor único; edição entre comparação e escrita pode ser perdida; mistura exata anterior/alvo é completada"}


# decisions/aux-plan.md, AUXP-04/H15: no second flock; the caller calculates both decisions inside this context.
@contextmanager
def locked_pair(main, aux):
    """Pair an Engine, or resolve an optional auxiliary Engine after acquiring the main lock."""
    if main.kind != 'main':
        raise ValueError('Expected main and auxiliary engines')
    with main.locked():
        # AUXP-04/H9/H15c: discovery and the decision to restore must share the same exclusion.
        aux = aux() if callable(aux) else aux
        if aux is None:
            yield main, None
            return
        if aux.kind != 'auxiliary' or main is aux:
            raise ValueError('Expected main and auxiliary engines')
        if main.directory.absolute() != aux.directory.absolute() or main.backend is not aux.backend:
            raise ValueError('Paired engines require the same directory and backend')
        if len({main.state_name, main.journal_name, aux.state_name, aux.journal_name}) != 4:
            raise ValueError('Paired records must be disjoint')
        if aux._directory_fd is not None:
            raise RuntimeError('Auxiliary engine already paired')
        aux._directory_fd, aux._holder = main._directory_fd, main._holder
        try:
            aux.load_state_locked()
            yield main, aux
        finally:
            aux._directory_fd, aux._holder = None, None



# decisions/s3-plan.md, R2: use native Changes, never credential-bearing model-switch resolution.
class NativeBackend:
    """Native Changes only; no model switch or credential-bearing resolution."""
    can_store_null = False

    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        from .inventory import read_document
        return read_document(self.path)

    def write(self, updates, unset):
        from hermes_cli.config_backend import Changes, write_changes
        write_changes(self.path, Changes(document=None, set=updates, unset=tuple(unset), extra_content_on_create=None))
