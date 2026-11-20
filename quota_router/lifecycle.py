# Implements decisions/hqr-20-amendment.md, sections 3/5/13 and AC-17/18/23/24; decisions/s3-plan.md, "Escopo";
# decisions/hqr-38-spec.md, D-28 to D-31 (states and safety net groups); decisions/aux-plan.md, D-AUXP-8 (map approval).
"""Optional OFF/Observe/Auto management for next-task routes; no request interception."""
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import platform
from pathlib import Path
import sys
from contextvars import copy_context
from threading import Event, RLock, Thread
import time
from typing import Any

from . import VERSION, storage, groups, auxiliary
from .identity import selection
from .inventory import cron_origins, native_profile, native_sources, read as read_inventory
from .mapping import approved_auxiliary, approved_base, catalog_gate, effective_map, native_catalogs, propose
from .apply import FETCH_WAIT, LOCK_DEADLINE, Engine, LockBusy, NativeBackend, locked_pair
from .compat import native_compatibility, native_auxiliary_compatibility
from .events import HOOKS, READER_CONTEXT, REFRESH, TRIGGER, HookWorker
from .policy import decide, eligibility, fallback_chain
from .readings import collect, last_known_valid, native_importer, reusable, revalidate
from .render import render
from .settings import DEFAULTS, PROVIDERS, load as load_settings, validate

USAGE = ("Usage: /quota-router status | explain | mode off|observe|auto | "
         "config [show | set <key> <value> | reset <key> | approve-map base|fable|astra|fable+astra|auxiliary] [--json]")
AUTO_REASON = "Auto requires an approved map, valid settings and qualified native source"
PLUGIN_DATA = Path('plugin-data') / 'hermes-quota-router'
LOG = logging.getLogger(__name__)
# Incidente 19/11: a sync slash command is not time-bounded by Hermes; it waits at most this long for every lock.
COMMAND_LOCK_BUDGET_S = 10
# Seconds a read-only command waits for a stale quota fetch before answering on cached/last-known readings.
COMMAND_FETCH_WAIT_S = 3
# Revisão S1, F3: Hermes abandons a plugin load after plugins.load_timeout_seconds (10 s) and another process's cycle on
# the same profile holds auto.lock for 22-35 s, so register() waits at most this long and then defers Auto's start.
REGISTER_LOCK_BUDGET_S = 3
# A cycle slower than this is logged as a WARNING (agent.log); each cycle's phases go to CYCLE_TIMINGS.
SLOW_CYCLE_WARNING_S = 10
CYCLE_TIMINGS = 'cycle_timings.json'
BUSY = "O Quota Router está executando um ciclo agora; tente novamente em alguns segundos."
MODE_CHANGED_BUSY = ("Modo alterado para {mode}. O status não pôde ser lido agora porque o Quota Router está executando um "
                     "ciclo; use `/quota-router status` em alguns segundos.")


class ModeChangedBusy(Exception):
    """Revisão S1, F5: the mode change was saved and applied, but the final status ran out of the lock budget."""
    def __init__(self, mode):
        super().__init__(mode)
        self.mode = mode


def _utcnow():
    return datetime.now(timezone.utc)


class BackgroundFetch:
    """One quota fetch for a command, on private copies of the cache; the manager merges it once, under its lock."""
    def __init__(self, manager, max_age_s, limited):
        self.manager, self.max_age_s, self.limited = manager, max_age_s, limited
        self.base_cache, self.base_good = dict(manager.cache), dict(manager.last_good())
        self.cache, self.last_good = dict(self.base_cache), dict(self.base_good)
        self.done, self.merged, self.result = Event(), False, None

    def run(self):
        LOCK_DEADLINE.set(None)
        FETCH_WAIT.set(None)
        m = self.manager
        try:
            self.result = collect(PROVIDERS, m.clock(), self.max_age_s, cache=self.cache, importer=m.importer, clock=m.clock,
                                  last_good=self.last_good, no_carry=self.limited)
        except Exception:
            self.result = None
        finally:
            self.done.set()
        with m.lock:
            m.merge_fetch(self)


class Management:
    def __init__(self, ctx, importer=None, sources=None, clock=None, profile=None, backend=None, data_dir=None, compatible=None, catalogs=None,
                 auxiliary_compatible=None, auxiliary_registry=None, refused=None):
        self.ctx = ctx
        self.profile = profile or native_profile
        self.lock = RLock()
        self.read_failed = False
        self.importer = importer or native_importer
        self.sources = sources or native_sources
        self.clock = clock or _utcnow
        self.cache = {}
        self._last_good = None
        self._last_good_loaded = False
        self._saved = {}
        self._last_hook_cycle = None
        self._fetch = None
        self.refresh_pending = False
        self.phases = {}
        # Revisão F1–F5, R3/R5: last forced refresh and last rate-limit signal per provider.
        self._forced = {}
        self.rate_limited = {}
        self.queries = 0
        self.queries_total = 0
        self.preferences = {}
        self.preference_routes = {}
        self.auxiliary_preference = {}
        self.decision_now = None
        self.backend = backend
        self.data_dir = data_dir
        self.compatible = compatible or native_compatibility
        self.catalogs = catalogs or native_catalogs
        self.engine = None
        self.aux_engine = None
        self.auxiliary_compatible = auxiliary_compatible or native_auxiliary_compatibility
        self.auxiliary_registry = auxiliary_registry or auxiliary.native_registry
        self.worker = None
        self.hook_registrations = []
        # Revisão F1–F5, R4: register() refuses Auto when the install path disagrees with the registering home.
        self.auto_failure = refused
        saved = self.read("mode", "off")
        self.mode = saved if saved in ("off", "observe") else "unavailable"
        self.closed = False
        self.deployment, self.identity_evidence = selection(self.read("deployment"))
        # Revisão da simplificação, F1: the applied route seeds the hysteresis only once per role, and only for the
        # settings found when the retained state was loaded at startup; any later change starts a new history.
        # Revisão S1, F3: a startup load deferred by a busy auto.lock seeds on the first load that completes.
        self.restart_seed = None
        self.seed_pending = True
        # Revisão S1, F3: Auto saved and qualified, hooks registered, but begin deferred to the first cycle or command.
        self.auto_pending = False
        token = LOCK_DEADLINE.set(time.monotonic() + REGISTER_LOCK_BUDGET_S)
        try:
            try:
                self.load_retained_state()
            except LockBusy:
                LOG.warning('Quota Router: auto.lock busy at load; retained state loads on first use')
            if saved == "auto" and self.auto_check()["ok"]:
                self.set_mode("auto")
                try:
                    started = self.start_auto()
                except LockBusy:
                    started = self.defer_auto()
                if started and not self.auto_pending:
                    try:
                        self.loaded_engines()
                    except LockBusy:
                        pass
        finally:
            LOCK_DEADLINE.reset(token)

    def load_retained_state(self):
        self._load_retained_state()
        if self.seed_pending:
            self.seed_pending = False
            if self.engine is not None:
                self.restart_seed = {'settings': self.revision(self.settings()[0]), 'done': set()}

    def _load_retained_state(self):
        try:
            if self.data_dir is None:
                constants = sys.modules.get('hermes_constants')
                if constants is None:
                    return
                directory = constants.get_hermes_home() / PLUGIN_DATA
            else:
                directory = Path(self.data_dir)
            try:
                with storage.directory(directory) as fd:
                    retained = False
                    for name in ('state.json', 'aux-state.json', 'aux-journal.json'):
                        try:
                            handle = storage.open_record(fd, name)
                        except FileNotFoundError:
                            continue
                        os.close(handle)
                        retained = True
                    if not retained:
                        return
            except FileNotFoundError:
                return
            if self.data_dir is None:
                self.data_dir = directory
                self.backend = NativeBackend(directory.parent.parent / 'config.yaml')
            self.engine = self.new_engine()
            self.loaded_engines()
        except LockBusy:
            # Incidente 19/11: a command's lock budget ran out; nothing was loaded, so retry on the next call.
            self.engine = None
            raise
        except Exception:
            self.auto_failure = 'invalid_auto_state'

    # decisions/aux-plan.md, H9/H20: even an initially OFF instance must enter auto.lock before deciding nothing is retained.
    def ensure_retained_engine(self):
        if self.engine is not None:
            return
        if self.data_dir is None:
            constants = sys.modules.get('hermes_constants')
            if constants is None:
                return
            self.data_dir = constants.get_hermes_home() / PLUGIN_DATA
        if self.backend is None:
            self.backend = NativeBackend(Path(self.data_dir).parent.parent / 'config.yaml')
        self.engine = self.new_engine()

    def new_engine(self):
        return Engine(self.data_dir, self.backend, compatible=lambda: self.compatible(), snapshot=self.retained_report)

    # decisions/aux-plan.md, AUXP-04: create no auxiliary Engine while disabled and without retained records.
    def ensure_auxiliary(self):
        self.engine.require_locked()
        if self.aux_engine is not None:
            return self.aux_engine
        settings, _invalid = self.settings()
        retained = any(self.engine.read_record(name) is not None for name in ('aux-state.json', 'aux-journal.json'))
        if settings['consumers.auxiliary'] or retained:
            self.aux_engine = Engine(self.engine.directory, self.backend, compatible=self.auxiliary_check,
                                     state_name='aux-state.json', journal_name='aux-journal.json', kind='auxiliary')
        return self.aux_engine

    def auxiliary_check(self):
        try:
            main = self.compatible()
            if main.get('ok') is not True:
                return dict(main, fingerprint_failure=False)
            return self.auxiliary_compatible()
        except Exception:
            return {'ok': False, 'reasons': ['auxiliary_compatibility_unavailable'], 'fingerprint_failure': True}

    def loaded_engines(self):
        with locked_pair(self.engine, self.ensure_auxiliary):
            self.engine.loaded_locked(self.clock().timestamp())
            if self.aux_engine is not None:
                self.aux_engine.loaded_locked(self.clock().timestamp())

    # decisions/s3-plan.md, "Escopo" and D-37: approved map, valid settings and qualified source are mandatory.
    def auto_check(self):
        settings, invalid = self.settings()
        if self.read_failed or invalid:
            return {"ok": False, "reasons": ["invalid_settings"]}
        if not settings["roles"]:
            return {"ok": False, "reasons": ["approved_map_required"]}
        # D-37: enrollment is per profile; a profile enrolls by enabling its own copy with its own approved map.
        if self.auto_failure:
            return {"ok": False, "reasons": [self.auto_failure]}
        try:
            return self.compatible()
        except Exception:
            return {"ok": False, "reasons": ["native_source_unavailable"]}

    def start_auto(self):
        if self.worker is not None:
            return True
        try:
            if not self.begin_auto():
                return False
            self.register_hooks()
            return True
        except LockBusy:
            self.dispose_hooks()
            raise
        except Exception:
            self.auto_unavailable()
            return False

    def begin_auto(self):
        if self.engine is None:
            if self.backend is None:
                from hermes_cli.config import get_config_path
                self.backend = NativeBackend(get_config_path())
            if self.data_dir is None:
                from hermes_constants import get_hermes_home
                self.data_dir = get_hermes_home() / PLUGIN_DATA
            self.engine = self.new_engine()
        with locked_pair(self.engine, self.ensure_auxiliary):
            if not self.engine.begin_locked():
                return False
            if self.aux_engine is not None:
                # AUXP-04: auxiliary qualification failure must not disable the already-qualified main consumer.
                if self.auxiliary_check().get('ok') is True and not self.aux_engine.begin_locked():
                    return False
        return True

    def register_hooks(self):
        self.worker = HookWorker(self.engine, self.hook_cycle, self.clock)
        for name in HOOKS:
            self.hook_registrations.append(self.ctx.register_hook(name, self.worker.callback(name)))

    def auto_unavailable(self):
        self.auto_failure = "hook_registration_or_storage_unavailable"
        self.dispose_hooks()
        self.set_mode("unavailable")

    # Revisão S1, F3: register() ran out of its lock budget. Hooks can only be registered while the plugin loads, so
    # they are registered now; the Auto begin runs on the first hook cycle (worker, normal locking) or command.
    def defer_auto(self):
        try:
            self.register_hooks()
        except Exception:
            self.auto_unavailable()
            return False
        self.auto_pending = True
        LOG.warning('Quota Router: auto.lock busy at load; Auto begins on the first cycle')
        return True

    def resume_auto(self):
        """Begin the Auto deferred by register(); False keeps it pending (recovery failed) and writes nothing."""
        try:
            if not self.begin_auto():
                return False
        except LockBusy:
            raise
        except Exception:
            self.auto_unavailable()
            return False
        self.loaded_engines()
        if self.seed_pending:
            self.seed_pending = False
            self.restart_seed = {'settings': self.revision(self.settings()[0]), 'done': set()}
        self.auto_pending = False
        return True

    def dispose_hooks(self):
        self.auto_pending = False
        if self.worker is not None:
            self.worker.close()
            self.worker = None
        for registration in reversed(self.hook_registrations):
            try:
                registration.dispose()
            except Exception:
                pass
        self.hook_registrations.clear()

    def wait_hooks(self):
        if self.worker is not None:
            self.worker.wait()

    # D-33: prompts, session starts and delegations can arrive in bursts; one cycle per interval is enough,
    # because readings are cached for limits.reading_max_age_s anyway. A rate limit forces a fresh reading.
    MIN_CYCLE_INTERVAL_S = 20
    # Revisão F1–F5, R3: a provider's reading is forced at most once per interval, and never inside its backoff.
    FORCED_REFRESH_INTERVAL_S = 30
    # Incidente 19/11: this runs only in the hook worker (HookWorker.run); Hermes' threads never wait for it.
    def hook_cycle(self):
        # The worker owns its lock deadline; quota reads in the background have no command fetch budget.
        token = FETCH_WAIT.set(None)
        try:
            with self.lock:
                if self.mode != "auto" or self.closed:
                    return
                now = self.clock().timestamp()
                forced = self.force_refresh(REFRESH.get() or (), now)
                if not forced and self._last_hook_cycle is not None and now - self._last_hook_cycle < self.MIN_CYCLE_INTERVAL_S:
                    return
                self._last_hook_cycle = now
                try:
                    self.status()
                except LockBusy:
                    # The next hook may retry immediately; contention is not a completed cycle.
                    self._last_hook_cycle = None
                    raise
        finally:
            FETCH_WAIT.reset(token)

    def force_refresh(self, providers, now):
        forced = False
        for provider in providers:
            if provider not in PROVIDERS:
                continue
            self.rate_limited[provider] = now
            last = self._forced.get(provider)
            if last is not None and now - last < self.FORCED_REFRESH_INTERVAL_S:
                continue
            cached = self.cache.get(provider) or {}
            if cached.get('state') == 'unknown' and reusable(cached, self.clock(), 0):
                # README.md, HQR-35: the failure's backoff (retry_at) also binds a rate-limit refresh.
                continue
            self.cache.pop(provider, None)
            self._forced[provider] = now
            forced = True
        return forced

    def apply_decisions(self, settings, found, inventory, timing=None):
        with locked_pair(self.engine, self.ensure_auxiliary):
            try:
                if not self.engine.recover_locked():
                    return
                if self.aux_engine is not None:
                    if not self.aux_engine.recover_locked():
                        # No new main or auxiliary write after recovery failure in either journal (AUXP-04).
                        # An unqualified empty auxiliary engine has nothing to recover; main can still run.
                        if self.aux_engine.read_record('aux-journal.json'):
                            return
                decisions = self.apply_current(settings, found, paired=True)
                return decisions, self.reports_locked()
            finally:
                if timing is not None:
                    # Revisão S1, F4: the timings record is read, extended and replaced while auto.lock is held.
                    self.note_cycle(*timing)

    # decisions/aux-plan.md, AUXP-04/H13: one validated snapshot for both reports, inside the operative lock.
    def reports_locked(self):
        self.engine.require_locked()
        result = self.engine.report(self.clock().timestamp())
        if self.aux_engine is not None:
            self.aux_engine.require_locked()
            report = self.aux_engine.report(self.clock().timestamp())
            report['restoration_pending'] = bool(self.aux_engine.read_record('aux-journal.json') or
                any(entry.get('active') for entry in self.aux_engine.state.get('groups', {}).values()))
            result['auxiliary'] = report
        return result

    # AUXP-04/H13/H20: preserve report(now) for readers while durable Engines own the synchronized snapshot boundary.
    def retained_report(self, now):
        loading_auxiliary = self.aux_engine is None
        with locked_pair(self.engine, self.ensure_auxiliary):
            if loading_auxiliary and self.aux_engine is not None:
                self.aux_engine.loaded_locked(now)
            return self.reports_locked()

    def apply_current(self, settings, found, paired=False):
        # AUXP-04: paired callers hold auto.lock across the reread, decision and both engine cycles.
        if paired:
            settings, invalid = self.settings()
            if invalid or self.read_failed:
                return
            self.decision_now = self.clock()
            found = revalidate(found, self.decision_now, settings['limits.reading_max_age_s'])
        # decisions/hqr-20-amendment.md, AC-20: recover first, then reread routes before calculating the next decision.
        document = self.backend.read()
        fresh = read_inventory(document, [])
        decisions = self.decisions(fresh, propose(fresh, found, settings), found, settings, document)
        enabled = set()
        selections = {}
        if settings["consumers.conversation"]:
            enabled.add("conversation")
        if settings["consumers.subagents"]:
            enabled.update(r["name"] for r in fresh.get("routes", []) if r["name"] in settings["roles"])
        # decisions/hqr-38-spec.md, D-29: each enrolled group carries its own safety net group, enabled and restored with it.
        enabled.update([groups.fallback_group(role) for role in enabled])
        items = dict(decisions.get("routes", {}), conversation=decisions.get("conversation", {}))
        for role, decision in items.items():
            if role in enabled and decision.get("state") == "decided" and role in settings["roles"] and decision.get("choice"):
                provider = decision["choice"]
                selections[role] = dict(settings["roles"][role][provider], provider=provider, tier=decision["tier"])
            if role in enabled and role in settings["roles"] and decision.get("state") in ("decided", "route_retained", "no_candidate"):
                net = decision.get('safety_net')
                if net is not None:
                    selections[groups.fallback_group(role)] = ({'blocked_fields': net['blocked_fields']}
                        if net.get('state') == 'group_blocked' else {"chain": net["chain"]})
        if paired:
            started = time.monotonic()
            self.engine.cycle_locked(selections, enabled=enabled, now=self.clock().timestamp())
            self.phases['main'] = time.monotonic() - started
            if self.aux_engine is not None:
                self.engine.checkpoint('main_cycle_done')
                aux = decisions['auxiliary']
                if self.auxiliary_check().get('ok') is True and (not settings['consumers.auxiliary'] or aux['registry_ok']):
                    choices = {auxiliary.PREFIX + task: dict(item['cells'][item['choice']], provider=item['choice'])
                               for task, item in aux['tasks'].items() if item.get('choice') and item.get('enrolled')}
                    enabled_aux = {auxiliary.PREFIX + task for task, item in aux['tasks'].items() if item.get('enrolled')}
                    started = time.monotonic()
                    self.aux_engine.cycle_locked(choices, enabled=enabled_aux, now=self.clock().timestamp())
                    self.phases['auxiliary'] = time.monotonic() - started
        else:
            self.engine.cycle(selections, enabled=enabled, now=self.clock().timestamp())
        # Only a confirmed persisted target may advance the preference's expected route.
        document = self.backend.read()
        for role, entry in self.engine.state['groups'].items():
            if groups.is_fallback(role) or not entry.get('active') or groups.preconditions(document, role) or groups.project(document, role) != entry.get('last'):
                continue
            values = entry['last']
            keys = groups.CONVERSATION if role == 'conversation' else groups.FIELDS
            current = {name: values[key].get('value') for name, key in
                       zip(('provider', 'model', 'effort'), (keys[0], keys[1], keys[4]))}
            self.preference_routes[role] = self.route_revision(role, current, document)
        return decisions

    def read(self, key, default=None):
        try:
            return self.ctx.get_config(key, default)
        except Exception:
            self.read_failed = True
            return "unavailable"

    def close(self):
        with self.lock:
            self.closed = True
            self.dispose_hooks()
            self.set_mode("off")

    def settings(self):
        return load_settings(lambda key, default: self.read(key, default))

    def observing(self):
        return not self.closed and self.mode in ("observe", "auto")

    # D-35: the last successful reading per provider survives a restart, so a first failed fetch is not "unknown".
    LAST_GOOD = 'last_readings.json'
    LAST_FAILURES = 'last_failures.json'

    # Revisão F1–F5, R7: load once an Engine exists (not an empty memo from before it), keep only readings in the
    # normalized shape, and let this process's newer readings win over the stored ones.
    def last_good(self):
        if self._last_good is None or (not self._last_good_loaded and self.engine is not None):
            current = self._last_good or {}
            stored = {}
            if self.engine is not None:
                self._last_good_loaded = True
                try:
                    record = self.engine.read_record(self.LAST_GOOD, {})
                    if isinstance(record, dict):
                        stored = {p: r for p, r in record.items() if p in PROVIDERS and last_known_valid(p, r)}
                    self._saved[self.LAST_FAILURES] = json.dumps(self.engine.read_record(self.LAST_FAILURES, {}), sort_keys=True)
                except Exception:
                    pass
                self._saved[self.LAST_GOOD] = json.dumps(stored, sort_keys=True)
            stored.update(current)
            self._last_good = stored
        return self._last_good

    # Revisão F1–F5, R6/R7: each record is published only when its content changes, including an emptied failure set.
    def save_last_good(self, found):
        if self.engine is None:
            return
        failed = {p: {'reason': r.get('failed_reason') or r.get('reason'), 'at': r.get('failed_at'),
                      'kept_last_known': bool(r.get('last_known'))}
                  for p, r in found.items() if r.get('state') != 'ok' or r.get('last_known')}
        records = {self.LAST_GOOD: self.last_good(), self.LAST_FAILURES: failed}
        try:
            # Own records with atomic replace: no shared state is read, so the Auto lock is not taken here.
            with storage.directory(self.engine.directory) as fd:
                for name, value in records.items():
                    text = json.dumps(value, sort_keys=True)
                    if self._saved.get(name) != text:
                        # Diagnosis only: reason codes and time, never error text or credentials.
                        storage.publish(fd, name, value)
                        self._saved[name] = text
        except Exception:
            pass

    def readings(self, settings):
        max_age = settings["limits.reading_max_age_s"]
        # R5: a provider that just answered with a rate limit is not decided on its last known reading.
        limited = set(self.rate_limited)
        wait = FETCH_WAIT.get()
        stale = [p for p in PROVIDERS if not reusable(self.cache.get(p), self.clock(), max_age)]
        found = None
        if wait is None or not stale:
            def read():
                return collect(PROVIDERS, self.clock(), max_age, cache=self.cache, importer=self.importer, clock=self.clock,
                               last_good=self.last_good(), no_carry=limited)
            # D-33: the hook caller's context carries the profile secret scope Claude's quota read needs.
            caller = READER_CONTEXT.get()
            found, issued = caller.copy().run(read) if caller is not None else read()
            self.absorb(found, issued, limited)
        else:
            # Incidente 19/11: a read-only command never blocks on a fetch beyond `wait`; the fetch goes on in the
            # background and fills the cache, and the answer uses cached/last-known readings meanwhile.
            fetch = self.background_fetch(max_age, limited)
            if fetch.done.wait(wait):
                found = self.merge_fetch(fetch)
            if found is None:
                found, _ = collect(PROVIDERS, self.clock(), max_age, cache=dict(self.cache), importer=lambda: None,
                                   clock=self.clock, last_good=dict(self.last_good()), no_carry=limited)
                for provider in stale:
                    reading = found[provider]
                    key = 'failed_reason' if reading.get('last_known') else 'reason'
                    if reading.get(key) == 'reader_unavailable':
                        found[provider] = dict(reading, **{key: 'refresh_pending'})
                self.refresh_pending = True
        # One decision time for every candidate: a reading that expired or crossed a reset meanwhile is unknown.
        self.decision_now = self.clock()
        return revalidate(found, self.decision_now, max_age)

    def absorb(self, found, issued, limited):
        for provider in limited:
            reading = found.get(provider) or {}
            if reading.get('state') == 'ok' and not reading.get('last_known'):
                self.rate_limited.pop(provider, None)
        self.save_last_good(found)
        self.queries += issued
        self.queries_total += issued

    def background_fetch(self, max_age_s, limited):
        """The fetch in flight (single flight), or a new one in a daemon thread with the caller's context."""
        if self._fetch is None or self._fetch.merged:
            self._fetch = BackgroundFetch(self, max_age_s, limited)
            Thread(target=copy_context().run, args=(self._fetch.run,), name='quota-router-refresh', daemon=True).start()
        return self._fetch

    def merge_fetch(self, fetch):
        """Merge a finished BackgroundFetch once (caller holds self.lock); returns its readings, or None."""
        if fetch.merged:
            return None
        fetch.merged = True
        if self._fetch is fetch:
            self._fetch = None
        if fetch.result is None or self.closed:
            return None
        found, issued = fetch.result
        self.cache.update({p: r for p, r in fetch.cache.items() if r is not fetch.base_cache.get(p)})
        self.last_good().update({p: r for p, r in fetch.last_good.items() if r is not fetch.base_good.get(p)})
        self.absorb(found, issued, fetch.limited)
        return found

    def note_cycle(self, started, readings_s):
        """Incidente 19/11: keep each cycle's trigger and phase durations (no secrets); warn when it is slow.

        The caller holds auto.lock (apply_decisions), so concurrent processes never lose each other's records.
        """
        seconds = {'readings': readings_s, 'main': self.phases.get('main'), 'auxiliary': self.phases.get('auxiliary'),
                   'total': time.monotonic() - started}
        seconds = {k: None if v is None else round(v, 3) for k, v in seconds.items()}
        trigger = TRIGGER.get() or 'command'
        record = {'at': self.clock().timestamp(), 'trigger': trigger, 'seconds': seconds}
        if seconds['total'] > SLOW_CYCLE_WARNING_S:
            LOG.warning('Quota Router: slow cycle %.1f s (trigger %s; readings %s s, main %s s, auxiliary %s s)',
                        seconds['total'], trigger, seconds['readings'], seconds['main'], seconds['auxiliary'])
        try:
            records = self.engine.read_record(CYCLE_TIMINGS, [])
            records = (records if isinstance(records, list) else []) + [record]
            self.engine.persist(CYCLE_TIMINGS, records[-32:])
        except Exception:
            pass

    def set_mode(self, mode):
        if mode != self.mode:
            self.queries = 0
            self.cache.clear()
        self.mode = mode

    def revision(self, settings, *parts):
        """Preference revision: any change of settings, candidate pair or current route starts a new preference history."""
        relevant = {k: v for k, v in settings.items() if k != "mode"}
        return hashlib.sha256(json.dumps([relevant, *parts], sort_keys=True).encode()).hexdigest()[:16]

    def status(self, detail=False):
        # Correção 2026-11-18: a failed settings read makes this answer incomplete; it must not suspend Auto and block
        # the OFF restoration for the rest of the process, so every operation starts from its own reads.
        self.read_failed = False
        self.refresh_pending = False
        self.phases = {}
        started = time.monotonic()
        if self.engine is None:
            self.load_retained_state()
        saved = self.read("mode", "off")
        deployment_saved, saved_evidence = selection(self.read("deployment"))
        identity_changed = (deployment_saved, saved_evidence) != (self.deployment, self.identity_evidence)
        settings, invalid = self.settings()
        healthy = not self.read_failed and saved in ("off", "observe", "auto") and self.mode != "unavailable"
        result = {
            "ok": healthy,
            "integrity": "observe_only_no_route_writes" if healthy else "settings_or_mode_unavailable",
            "version": VERSION,
            "deployment": self.deployment,
            "deployment_saved": deployment_saved,
            "identity_evidence": self.identity_evidence,
            "identity_saved_evidence": saved_evidence,
            "installed_verified": False,
            "compatibility": {
                "python": platform.python_version(),
                "host": "unqualified",
                "source_qualified": False,
                "lifecycle": "requires_installed_smoke",
                "auto": "unavailable",
                "surfaces": "best_effort_next_tasks",
            },
            "mode_saved": saved if saved in ("off", "observe", "auto") else "invalid",
            "mode_effective": "unloaded" if self.closed else self.mode,
            "effective_scope": "this_plugin_instance_only",
            "restart_required": not self.closed and (saved != self.mode or identity_changed),
            "draining": "not_applicable_no_admission_in_S1",
            "auto_available": False,
            "auto_reason": AUTO_REASON,
            "settings": settings,
            "settings_invalid": invalid,
            "profile": self.profile(),
            "enrollment": {"state": "enrolled", "scope": "this_profile",
                           "other_profiles": "a profile without this plugin enabled is not enrolled; see `hermes -p <profile> plugins list`"},
            "quota": {"state": "unknown", "source": None},
            "extra_inferences": 0,
        }
        if self.observing():
            # Inventory first: its I/O must not age the readings after their decision-time check.
            document, jobs = self.sources()
            inventory = read_inventory(document, jobs)
            result["cron_origins"] = cron_origins(document, jobs)
            fetched = time.monotonic()
            found = self.readings(settings)
            readings_s = time.monotonic() - fetched
            source = "native_account_usage" if self.importer is native_importer else "injected_reader"
            # decisions/hqr-38-spec.md, "Regras de decisão": account-level state per provider for status and render.
            states = {p: eligibility(r, settings, self.decision_now)["state"] for p, r in found.items()}
            result["quota"] = {"state": "observed", "source": source, "providers": found, "states": states}
            if self.refresh_pending:
                result["quota"]["refresh"] = "pending"
            self.evaluate(result, settings, invalid, found, detail, inventory, document)
            if self.mode == "auto":
                ready = self.auto_check()
                if self.refresh_pending:
                    # A view that skipped a stale fetch never writes routes; the next hook cycle applies.
                    result["auto_deferred"] = "quota_refresh_pending"
                elif ready["ok"] and self.engine is not None and self.auto_pending and not self.resume_auto():
                    result["auto_suspended"] = ["auto_start_pending"]
                elif ready["ok"] and self.engine is not None and self.mode == "auto":
                    applied = self.apply_decisions(settings, found, inventory, (started, readings_s))
                    if applied is not None:
                        applied_decisions, result['applied'] = applied
                        if applied_decisions is not None and self.aux_engine is not None:
                            result['decisions'].update({key: applied_decisions[key] for key in ('conversation', 'routes', 'cron', 'auxiliary')})
                            result['routing_blocks'] = applied_decisions.get('routing_blocks', {})
                            result['coverage']['auxiliary'] = applied_decisions['auxiliary']['coverage']
                else:
                    result["auto_suspended"] = ready["reasons"]
        ready = self.auto_check()
        result["subagents"] = self.subagents_status()
        result["auto_available"] = ready["ok"]
        result["auto_reason"] = None if ready["ok"] else ", ".join(ready["reasons"])
        result["compatibility"]["auto"] = "available" if ready["ok"] else "unavailable"
        # D18: source qualification is distinct from map approval, effective Auto and installed lifecycle evidence.
        try:
            native = self.compatible()
        except Exception:
            native = {'ok': False, 'reasons': ['native_source_unavailable']}
        if not native.get('ok'):
            ready = dict(ready, ok=False, reasons=sorted(set(ready.get('reasons', []) + native.get('reasons', ['native_source_unavailable']))))
            result.update(auto_available=False, auto_reason=', '.join(ready['reasons']))
            result['compatibility']['auto'] = 'unavailable'
            if self.mode == 'auto':
                result['auto_suspended'] = ready['reasons']
        result['compatibility'].update(source_qualified=native.get('ok') is True,
                                       host=native.get('host', 'qualified') if native.get('ok') else 'unqualified',
                                       reasons=native.get('reasons', []))
        for key in ('revision', 'qualified_revision', 'revision_note'):
            if key in native:
                result['compatibility'][key] = native[key]
        if native.get('ok'):
            result['draining'] = 'not_applicable_no_request_interception'
        if self.mode == 'auto' and healthy:
            result['integrity'] = 'auto_best_effort_native_config'
        result['compatibility']['auxiliary'] = self.auxiliary_check()
        if self.engine is not None:
            # AUXP-04/H13/H20: retained reports reload validated state under the same shared lock, not an instance cache.
            if 'applied' not in result:
                # Durable Engines expose a synchronized snapshot; read-only report providers keep report(now).
                report = getattr(self.engine, 'snapshot', None) or self.engine.report
                result['applied'] = report(self.clock().timestamp())
            result["coverage"] = dict(result.get("coverage", {}), hooks="unqualified_until_installed_run",
                                      task_generation="native_session_store_unqualified")
        self.reflect_auxiliary_blocks(result)
        self.reflect_final_blocks(result, ready, settings)
        # Queries issued since the last effective mode change (zero in OFF); quota_queries_total covers this instance.
        result["quota_queries"] = self.queries
        result["quota_queries_total"] = self.queries_total
        return result

    # D18/AC-17: a late exclusion or suspension must override an earlier optimistic preview in the same response.
    def reflect_final_blocks(self, result, ready, settings):
        decisions = result.get('decisions') or {}
        if 'conversation' not in decisions:
            return
        blocks = result.setdefault('routing_blocks', {})
        applied = result.get('applied') or {}
        exclusions = applied.get('groups_out', {}) if applied.get('auto_declared') else {}
        items = dict(decisions.get('routes', {}), conversation=decisions['conversation'])
        for role, decision in items.items():
            if decision.get('state') == 'disabled_by_setting':
                continue
            excluded = exclusions.get(role, [])
            suspended = bool(settings['roles']) and not ready.get('ok')
            fallback_excluded = exclusions.get(groups.fallback_group(role), [])
            if decision.get('safety_net') is not None and (fallback_excluded or excluded or suspended):
                self.block_safety_net(decision, role, fallback_excluded or excluded,
                                      ready.get('reasons', []) if suspended else [], blocks)
            if not excluded and not suspended:
                continue
            backend_reason = 'advanced_delegation_unavailable'
            fields = sorted(set((blocks.get(role) or {}).get('fields', []) + [field for field in excluded if field != backend_reason]))
            reasons = (blocks.get(role) or {}).get('reasons', [])
            if backend_reason in excluded:
                reasons = sorted(set(reasons + [backend_reason]))
            if suspended:
                reasons = sorted(set(reasons + ready.get('reasons', ['host_not_qualified'])))
            if fields or reasons:
                blocks[role] = {'fields': fields, 'reasons': reasons}
                state = 'backend_unavailable' if not fields and reasons == [backend_reason] else 'group_blocked'
                decision.update(state=state, choice=None, tier=None, would_change=None, proposal_change=None,
                                blocked_fields=fields, block_reasons=reasons)

    def explain(self):
        result = self.status(detail=True)
        if not self.observing():
            result["decisions"] = {"state": "not_observing"}
        return result

    def evaluate(self, result, settings, invalid, found, detail, inventory, document=None):
        proposal = propose(inventory, found, settings)
        decisions = self.decisions(inventory, proposal, found, settings, document)
        result["routing_blocks"] = decisions.get("routing_blocks", {})
        result["decided_at"] = self.decision_now.astimezone(timezone.utc).isoformat()
        result["decision_incomplete"] = bool(invalid) or self.read_failed or any(r["state"] != "ok" for r in found.values())
        result["coverage"] = {"not_governed": inventory.get("not_governed", []), "inventory": inventory.get("state"),
                              "bot_chat": "follows_profile_model_each_turn_HQR-24",
                              "managed_sessions": "created_before_a_decision_keep_their_copy"}
        result['coverage']['auxiliary'] = decisions.get('auxiliary', {}).get('coverage', {})
        displayed_map = effective_map(proposal, settings)
        if detail:
            result["map"] = displayed_map
            result["decisions"] = decisions
            return
        def brief(decision):
            keys = ("choice", "tier", "state", "reason", "resets", "partial_pins", "would_change", "proposal_change",
                    "catalog_note", "catalog_unverified", "catalog_missing", "blocked_fields", "block_reasons", "states",
                    "safety_net", "legacy_fallback_present")
            return {k: decision[k] for k in keys if decision.get(k) is not None}
        if decisions.get("state") == "inventory_unavailable":
            result["decisions"] = {"state": "inventory_unavailable", "provider_level": brief(decisions["provider_level"])}
            return
        result["decisions"] = {"variant": decisions["variant"], "map_status": displayed_map["status"], "map_notes": displayed_map["notes"],
                               "conversation": brief(decisions["conversation"]),
                               "routes": {name: brief(d) for name, d in decisions["routes"].items()},
                               "cron": brief(decisions["cron"]), "auxiliary": decisions["auxiliary"]}

    # D18/AC-17 and G2/G8: route presence and both wire fields participate in preference identity.
    def route_revision(self, role, current, document):
        projection = groups.project(document, role) if not groups.preconditions(document, role) else None
        return dict(current, route=self.revision({}, projection))

    def decide_role(self, role, table, current, found, settings, enabled, document=None, retained=None):
        if not enabled:
            return {"state": "disabled_by_setting", "choice": None, "tier": None}
        approved = settings["roles"].get(role)
        proposed = table.get(role) if table else None
        if approved == {"follows": "conversation"}:
            return {"state": "follows_conversation", "choice": None, "tier": None}
        pair = approved or proposed
        models = {p: pair[p]["model"] for p in pair} if pair else {}
        catalogs = self.catalogs()
        unverified = sorted(p for p in models if catalogs.get(p) is None)
        catalog_details = {"catalog_note": "IDs não verificados", "catalog_unverified": unverified} if unverified else {}
        blocked = {p: reason for p, model in models.items() if (reason := catalog_gate(p, model, catalogs))}
        # decisions/s3-plan.md, "Mapa aprovado": an absent approved ID blocks the role, not just one provider.
        if approved and "model_absent_from_catalog" in blocked.values():
            return dict(catalog_details, state="catalog_model_absent", choice=None, tier=None, reason="model_absent_from_catalog",
                        catalog_missing=sorted(p for p, reason in blocked.items() if reason == "model_absent_from_catalog"))
        now = {"provider": current.get("provider"), "model": current.get("model"), "effort": current.get("effort")}
        applied = (retained or {}).get('groups', {}).get(role) or {}
        applied_matches = (applied.get('active') and applied.get('generation') is not None and document is not None
                           and not groups.preconditions(document, role) and groups.project(document, role) == applied.get('values'))
        identity = self.route_revision(role, now, document) if document is not None else now
        key = (role, self.revision(settings, pair, identity))
        if self.mode == 'auto':
            observed = self.preferences.get(key)
            key = (role, self.revision(settings, pair))
            if self.preference_routes.get(role) != identity:
                self.preferences.pop(key, None)
            # decisions/hqr-20-amendment.md, D10; decisions/s3-delivery.md, G8: preserve only the exact Observe preference.
            if observed is not None:
                self.preferences[key] = observed
            self.preferences = {k: v for k, v in self.preferences.items() if k[0] != role or k == key}
            self.preference_routes[role] = identity
            # Correção 2026-11-18: preferences live in memory, so after a restart the route this plugin applied and
            # still finds intact is the preference the hysteresis protects; otherwise a restart flips close scores.
            seed = self.restart_seed
            fresh = seed is not None and role not in seed['done'] and seed['settings'] == self.revision(settings)
            if seed is not None:
                seed['done'].add(role)
            if (fresh and key not in self.preferences and applied.get('active') and applied.get('tier') == 'subscription'
                    and pair and current.get('provider') in pair
                    and document is not None and not groups.preconditions(document, role)
                    and groups.project(document, role) == applied.get('values')):
                self.preferences[key] = current['provider']
        decision: dict[str, Any] = decide(role, found, settings, self.decision_now, previous=self.preferences.get(key),
                                          models=models, blocked=blocked)
        # D-43: protect the configured provider, not the transient preference used for ranking.
        incumbent, challenger = now['provider'], decision['choice']
        retained_reason = None
        if challenger is not None and incumbent in models and challenger != incumbent:
            fresh_challenger = not found.get(challenger, {}).get('last_known')
            return_to_franchise = fresh_challenger and decision['tier'] == 'subscription' and applied_matches and applied.get('tier') == 'credits'
            if incumbent not in blocked and decision['states'].get(incumbent, 'unknown') == 'unknown':
                if not return_to_franchise:
                    retained_reason = 'incumbent_reading_unknown'
            elif not return_to_franchise:
                incumbent_carried = found.get(incumbent, {}).get('last_known')
                if not fresh_challenger or (incumbent not in blocked and incumbent_carried):
                    retained_reason = 'fresh_quota_pair_required'
        if retained_reason:
            decision.update(choice=None, tier=None, reason=retained_reason)
        if decision["tier"] == "subscription":
            self.preferences[key] = decision["choice"]

        def change(source):
            target = dict(source[decision["choice"]], provider=decision["choice"]) if source and decision["choice"] else None
            fields = []
            if target and approved and document is not None and not groups.preconditions(document, role):
                current_projection = groups.project(document, role)
                fields = [key for key, cell in groups.target(role, target).items() if cell != current_projection[key]]
            if not target or target == now and not fields:
                return None
            return dict({'from': now, 'to': target}, **({'fields': fields} if fields else {}))

        decision.update(catalog_details)
        # decisions/hqr-38-spec.md, D-28/D-29: the other provider's mapped model for the same role, when usable.
        if role != "cron" and pair and decision["choice"] is not None:
            decision["safety_net"] = fallback_chain(decision, pair)
        elif (role != 'cron' and pair and challenger is not None and retained_reason == 'incumbent_reading_unknown'
              and decision['states'].get(challenger) in ('free', 'pressured')
              and not found.get(challenger, {}).get('last_known')):
            # D-43: retain the primary route but refresh its separately governed fallback to known franchise.
            qualified = {challenger: decision['eligibility'][challenger]}
            decision['safety_net'] = fallback_chain(dict(decision, choice=challenger, eligibility=qualified), pair)
        decision["would_change"] = change(approved) if approved else None
        decision["proposal_change"] = None if approved else change(proposed)
        if retained_reason:
            decision["state"] = "route_retained"
        elif decision["choice"] is None:
            decision["state"] = "no_candidate"
        else:
            decision["state"] = "decided" if approved else "proposal_only"
        retained_with_paid_peer = (retained_reason == 'incumbent_reading_unknown' and challenger is not None
                                   and decision['eligibility'][challenger]['credits'])
        if role != 'cron' and enabled and approved and (decision['state'] == 'no_candidate' or
                (retained_with_paid_peer and decision.get('safety_net') is None)):
            managed = (retained or {}).get('safety_net', {}).get(groups.fallback_group(role), {})
            chain = managed.get('values', {}).get(groups.FALLBACK, {}).get('value')
            if managed.get('active') and managed.get('fallback_written') is True and chain:
                decision['safety_net'] = {'chain': [], 'excluded': {}}
        return decision

    def subagents_status(self):
        try:
            return self.compatible().get('subagents', {'ok': True, 'source': 'backend_contract'})
        except Exception:
            return {'ok': False, 'reason': 'advanced_delegation_unavailable'}

    def preview_fields(self, document, role, retained):
        """SOL-07: the same preconditions, null and external-edit gates for routes and their separate safety nets."""
        fields = groups.preconditions(document, role) + retained.get('groups_out', {}).get(role, [])
        if fields:
            return sorted(set(fields))
        projection = groups.project(document, role)
        if getattr(self.backend, 'can_store_null', False) is False:
            fields += [key for key, cell in projection.items() if cell.get('present') and cell.get('value') is None]
        section = 'safety_net' if groups.is_fallback(role) else 'groups'
        entry = retained.get(section, {}).get(role, {})
        if entry.get('active'):
            fields += [key for key, cell in projection.items() if cell != entry['values'].get(key)]
        return sorted(set(fields))

    @staticmethod
    def block_safety_net(decision, role, fields, reasons, blocks):
        group = groups.fallback_group(role)
        prior = blocks.get(group) or {}
        fields = sorted(set(fields + prior.get('fields', [])))
        reasons = sorted(set(reasons + prior.get('reasons', [])))
        blocks[group] = {'fields': fields, 'reasons': reasons}
        decision['safety_net'] = {'state': 'group_blocked', 'chain': None, 'blocked_fields': fields, 'block_reasons': reasons}

    def decisions(self, inventory, proposal, found, settings, document=None):
        if inventory.get("state") != "ok":
            return {"state": "inventory_unavailable", "provider_level": decide("general", found, settings, self.decision_now)}
        table = proposal["variants"].get(proposal["effective_variant"], {})
        if self.mode == 'auto':
            current_roles = {'conversation', 'cron'} | {route['name'] for route in inventory['routes']}
            self.preferences = {key: value for key, value in self.preferences.items() if key[0] in current_roles}
            self.preference_routes = {role: value for role, value in self.preference_routes.items() if role in current_roles}
        # D18/AC-17: preview uses the same enrollment gates as Auto, without capturing a baseline or writing.
        blocks = {}
        ready = self.auto_check() if settings['roles'] else {'ok': True}
        dependency = self.subagents_status()
        retained = self.engine.report(self.clock().timestamp()) if self.engine is not None else {}
        # D18/AC-17: explicit OFF ends enrollment; a later Auto begins with a new baseline.
        if not retained.get('auto_declared'):
            retained = {}
        def choose(role, current, enabled):
            fields, reasons = [], []
            if settings['roles'] and enabled:
                if role not in settings['roles']:
                    reasons.append('map_not_approved')
                if not ready.get('ok'):
                    reasons += ready.get('reasons', ['host_not_qualified'])
                if role != 'conversation' and not dependency.get('ok'):
                    reasons.append('advanced_delegation_unavailable')
                fields += self.preview_fields(document, role, retained)
                if fields or reasons:
                    self.preferences = {key: value for key, value in self.preferences.items() if key[0] != role}
                    self.preference_routes.pop(role, None)
                    blocks[role] = {'fields': sorted(set(fields)), 'reasons': sorted(set(reasons))}
                    state = 'backend_unavailable' if reasons == ['advanced_delegation_unavailable'] and not fields else 'group_blocked'
                    return dict(state=state, choice=None, tier=None, would_change=None, proposal_change=None,
                                blocked_fields=blocks[role]['fields'], block_reasons=blocks[role]['reasons'])
            decision = self.decide_role(role, table, current, found, settings, enabled, document, retained)
            net = decision.get('safety_net')
            if net is not None and document is not None:
                group = groups.fallback_group(role)
                fields = self.preview_fields(document, group, retained)
                if not fields:
                    baseline = groups.project(document, group)
                    target = groups.target(group, {'chain': net['chain']}, baseline)
                    managed = retained.get('safety_net', {}).get(group, {})
                    prior = baseline if managed.get('active') and managed.get('fallback_written') is True else None
                    fields += groups.effective_fallback_errors(document, group, target, net['chain'], prior=prior)
                if fields:
                    self.block_safety_net(decision, role, fields, [], blocks)
            if decision.get('state') not in ('decided', 'proposal_only', 'follows_conversation', 'route_retained'):
                blocks[role] = {'fields': [], 'reasons': [decision.get('reason') or decision['state']]}
            return decision
        routes = {route["name"]: choose(route["name"], route, settings["consumers.subagents"])
                  for route in inventory["routes"]}
        conversation_decision = choose('conversation', inventory['conversation'], settings['consumers.conversation'])
        if document is not None and document.get('fallback_model'):
            conversation_decision['legacy_fallback_present'] = 'fallback_model'
        cron = inventory["cron"]
        if not settings["consumers.cron"]:
            cron_decision = {"state": "disabled_by_setting", "choice": None, "tier": None}
        elif not cron["globals_writable"]:
            cron_decision = {"state": "blocked_partial_pins" if cron["partial_pins"] else "jobs_unavailable",
                             "partial_pins": cron["partial_pins"], "choice": None, "tier": None}
        else:
            conversation = inventory["conversation"]
            current = {"provider": cron["provider"] or conversation["provider"], "model": cron["model"] or conversation["model"],
                       "effort": conversation["effort"]}
            cron_decision = self.decide_role("cron", table, current, found, settings, True)
        return {
            "variant": proposal["effective_variant"],
            "conversation": conversation_decision,
            "routes": routes,
            "cron": cron_decision,
            "auxiliary": self.auxiliary_decisions(document, conversation_decision, found, settings),
            "routing_blocks": blocks,
        }

    # decisions/aux-plan.md, AUXP-02 and D-AUXP-6: the auxiliary origin is separate from choose and main preferences.
    def auxiliary_decisions(self, document, conversation, found, settings):
        pair = settings['roles'].get('conversation')
        key = self.revision(settings, pair)
        previous = self.auxiliary_preference.get(key)
        self.auxiliary_preference = {key: previous} if previous is not None else {}
        catalogs = self.catalogs()
        if conversation.get('state') in ('disabled_by_setting', 'group_blocked', 'backend_unavailable'):
            source = auxiliary.source_decision(pair, found, settings, self.decision_now, previous, catalogs)
            source.update(path='computed', conversation_state=conversation['state'])
        else:
            source = dict(conversation, path='conversation', conversation_state=conversation.get('state'))
        if source.get('tier') == 'subscription':
            self.auxiliary_preference = {key: source['choice']}
        enabled = settings['consumers.auxiliary']
        table = settings['auxiliary_map'] or approved_auxiliary()
        try:
            registry = self.auxiliary_registry()
        except Exception:
            registry = {'ok': False, 'tasks': {}}
        registered = registry.get('tasks', {}) if registry.get('ok') else {}
        check = self.auxiliary_check()
        retained = self.aux_engine.report(self.clock().timestamp()) if self.aux_engine is not None else {}
        entries = retained.get('groups', {}) if retained.get('auto_declared') else {}
        tasks = {}
        nodes = document.get('auxiliary', {}) if isinstance(document, dict) else {}
        nodes = nodes if isinstance(nodes, dict) else {}
        for task, cells in table.items():
            group = auxiliary.PREFIX + task
            raw = nodes.get(task)
            node = raw if isinstance(raw, dict) else {}
            # AUXP-03/H14: render only bounded route values, never rejected endpoints, keys or extra_body.
            current = {'provider': node.get('provider') if node.get('provider') in PROVIDERS + ('auto',) else None,
                       'model': auxiliary.safe_model(node.get('model')),
                       'effort': node.get('reasoning_effort') if node.get('reasoning_effort') in auxiliary.EFFORTS else None}
            item = {'current': current, 'cells': cells, 'choice': None, 'state': 'no_candidate', 'would_change': None,
                    'blocked_fields': [], 'block_reasons': [], 'enrolled': False,
                    'fallback_chain_present': 'fallback_chain' in node}
            def blocked(state, fields=(), reasons=()):
                item.update(state=state, choice=None, would_change=None, blocked_fields=sorted(set(fields)), block_reasons=list(reasons))
            entry = entries.get(group) or {}
            if not isinstance(raw, dict):
                blocked('not_in_map', ['auxiliary.' + task])
            elif not entry and node.get('provider') in (None, '', 'auto'):
                blocked('not_enrolled_auto')
            elif group in retained.get('groups_out', {}):
                blocked('group_blocked', retained['groups_out'][group])
            else:
                fields = auxiliary.preconditions(document, group)
                if not fields and entry.get('active'):
                    projection = auxiliary.project(document, group)
                    fields = ['auxiliary.' + task + '.' + field for field, value in projection.items()
                              if value != entry['values'].get(field)]
                if fields:
                    blocked('group_blocked', fields)
                elif auxiliary.enrollment_errors(document, task, cells):
                    blocked('not_in_map', auxiliary.enrollment_errors(document, task, cells))
                elif task in registered:
                    blocked('group_blocked', reasons=['plugin_task_collision'])
                elif not settings['auxiliary_map'] and self.mode == 'auto' and enabled:
                    blocked('not_in_map', reasons=['auxiliary_map_not_approved'])
                else:
                    item['enrolled'] = enabled and bool(settings['auxiliary_map'])
                    item.update(auxiliary.task_decision(cells, source.get('choice'), found, settings, self.decision_now, catalogs))
                    if not source.get('choice'):
                        blocked('source_map_not_approved' if not pair else source.get('state', 'no_candidate'),
                                reasons=[source.get('reason') or source.get('state', 'no_candidate')])
                        item['resets'] = source.get('resets', [])
                    else:
                        if item['choice'] == 'anthropic':
                            model = document.get('model', {})
                            from .routes import DEFAULT_ROUTES
                            if (isinstance(model, dict) and model.get('provider') == 'anthropic' and
                                    model.get('base_url') not in (None, '', DEFAULT_ROUTES['anthropic']['base_url'])):
                                blocked('group_blocked', ['model.base_url'])
                        if item['choice']:
                            selection = dict(cells[item['choice']], provider=item['choice'])
                            baseline = auxiliary.project(document, group)
                            target = auxiliary.target(group, selection, baseline)
                            if target != baseline:
                                item['would_change'] = {'from': current, 'to': selection,
                                                        'fields': ['auxiliary.' + task + '.' + f for f in target if target[f] != baseline[f]]}
                            elif item['state'] == 'decided':
                                item['state'] = 'unchanged'
                        if not enabled:
                            item['state'] = 'preview_only'
                    if enabled and not check.get('ok'):
                        blocked('suspended', reasons=check.get('reasons', ['auxiliary_compatibility_unavailable']))
                    elif enabled and not registry.get('ok'):
                        blocked('plugin_registry_unavailable', reasons=['plugin_registry_unavailable'])
            tasks[task] = item
        coverage = {'included': [task for task, item in tasks.items() if item.get('enrolled')],
                    'auto': [task for task, node in nodes.items() if auxiliary.safe_name(task) and isinstance(node, dict) and node.get('provider') in (None, '', 'auto')],
                    'not_in_map': [task for task in nodes if auxiliary.safe_name(task) and task not in settings['auxiliary_map']],
                    'inherited': {task: item['inherit_from'] for task, item in registered.items() if item.get('inherit_from') in table},
                    'image_gen': 'fixed_not_governed', 'bypass_sessions': 'outside_profile_configuration',
                    'in_flight': 'keep_started_route'}
        return {'source': source, 'tasks': tasks, 'registry_ok': registry.get('ok') is True, 'coverage': coverage}

    # decisions/aux-plan.md, AUXP-04/OFF: fingerprint-only failure permits main OFF, retaining an auxiliary obligation.
    def restore_engines(self):
        with locked_pair(self.engine, self.ensure_auxiliary):
            if self.aux_engine is None:
                if not self.engine.needs_restoration_locked():
                    return True
                if not self.auto_check()['ok']:
                    return False
                return self.engine.restore_locked(self.clock().timestamp())
            # AUXI3-R02: the auxiliary Engine waives map, catalog and registry, never the main Auto gate.
            pending = self.aux_engine.needs_restoration_locked() or self.engine.needs_restoration_locked()
            if pending and not self.auto_check()['ok']:
                return False
            if not self.engine.recover_locked():
                return False
            if self.aux_engine.needs_restoration_locked():
                if not self.aux_engine.restore_locked(self.clock().timestamp()):
                    # Revisão F1–F5, R9: since D-36 the auxiliary check is the main qualification, so a fingerprint-only
                    # failure (main qualified, auxiliary not) no longer occurs; the branch stays as a guard.
                    check = self.aux_engine.compatibility
                    if check.get('ok') is True or check.get('fingerprint_failure') is not True:
                        return False
            if self.engine.needs_restoration_locked():
                return self.engine.restore_locked(self.clock().timestamp())
            return True

    # decisions/aux-plan.md, H13: late qualification loss or external edit must clear an optimistic auxiliary preview.
    def reflect_auxiliary_blocks(self, result):
        tasks = ((result.get('decisions') or {}).get('auxiliary') or {}).get('tasks', {})
        applied = (result.get('applied') or {}).get('auxiliary') or {}
        check = result.get('compatibility', {}).get('auxiliary', {})
        for task, item in tasks.items():
            fields = applied.get('groups_out', {}).get(auxiliary.PREFIX + task, [])
            if fields:
                item.update(state='group_blocked', choice=None, would_change=None, blocked_fields=fields)
            elif result['settings']['consumers.auxiliary'] and not check.get('ok'):
                item.update(state='suspended', choice=None, would_change=None,
                            block_reasons=check.get('reasons', ['auxiliary_compatibility_unavailable']))

    def configure(self, parts):
        settings, invalid = self.settings()
        if parts in (["config"], ["config", "show"]):
            return {"ok": True, "settings": settings, "settings_invalid": invalid, "defaults": DEFAULTS}, None
        if len(parts) == 4 and parts[1] == "set":
            key, value = parts[2], parts[3]
            if key == "mode":
                return None, "Use /quota-router mode to change the mode"
            ok, normalized = validate(key, value)
            if not ok:
                return None, f"Invalid value for {key}: {normalized}; nothing was written"
        elif len(parts) == 3 and parts[1] == "reset" and parts[2] in DEFAULTS and parts[2] != "mode":
            key, normalized = parts[2], DEFAULTS[parts[2]]
        # decisions/aux-plan.md, D-AUXP-8: approving this map never enables a consumer or changes role approval.
        elif parts == ["config", "approve-map", "auxiliary"]:
            key = "auxiliary_map"
            ok, normalized = validate(key, approved_auxiliary())
            if not ok:
                return None, f"Proposed map is invalid ({normalized}); nothing was written"
        elif len(parts) == 3 and parts[1] == "approve-map":
            proposal = propose(read_inventory(*self.sources()), {}, settings)
            table = proposal["variants"].get(parts[2])
            if not table:
                return None, "Unknown map variant or inventory unavailable; nothing was written"
            table = approved_base() if parts[2] == "base" else table
            ok, normalized = validate("roles", table)
            if not ok:
                return None, f"Proposed map is invalid ({normalized}); nothing was written"
            key = "roles"
        else:
            return None, USAGE
        try:
            self.ctx.set_config(key, normalized)
        except Exception:
            return None, "Native plugin settings write failed; nothing changed"
        settings, invalid = self.settings()
        return {"ok": True, "settings": settings, "settings_invalid": invalid, "changed": {key: normalized}}, None

    def command(self, raw_args):
        """Readable chat text by default; the same result as strict JSON when the arguments include `--json`."""
        parts = raw_args.split() if isinstance(raw_args, str) else []
        as_json = "--json" in parts
        remaining = " ".join(p for p in parts if p != "--json")
        # Incidente 19/11: Hermes does not bound a sync command; every lock wait shares one budget, then it answers busy.
        deadline = time.monotonic() + COMMAND_LOCK_BUDGET_S
        if not self.lock.acquire(timeout=COMMAND_LOCK_BUDGET_S):
            return self.busy(as_json)
        tokens = (LOCK_DEADLINE.set(deadline), FETCH_WAIT.set(None if remaining == "apply" else COMMAND_FETCH_WAIT_S))
        try:
            output = self._command(remaining)
        except ModeChangedBusy as changed:
            return self.busy(as_json, changed.mode)
        # Revisão S1, F6: only the lock budget is busy; a network TimeoutError falls to the failure path below.
        except LockBusy:
            return self.busy(as_json)
        except Exception:
            # Native parsers and storage exceptions may embed credentials; retain journals but never echo the exception.
            self.auto_failure = 'native_state_or_config_unavailable'
            output = self.dump({"ok": False, "mode_effective": "unloaded" if self.closed else self.mode,
                                "auto_available": False, "auto_reason": self.auto_failure,
                                "error": "Native state/config unavailable; further Auto writes suspended until reload"})
        finally:
            FETCH_WAIT.reset(tokens[1])
            LOCK_DEADLINE.reset(tokens[0])
            self.lock.release()
        if as_json:
            return output
        payload = json.loads(output)
        name = parts[0] if parts and parts[0] in ("status", "explain", "config", "mode") else "status"
        try:
            return render(name, payload)
        except Exception:
            return "Não foi possível montar o texto do resultado. Use `/quota-router status --json` para ver os dados."

    def busy(self, as_json, changed=None):
        message = BUSY if changed is None else MODE_CHANGED_BUSY.format(mode=changed)
        if not as_json:
            return message
        payload = {"ok": changed is not None, "busy": True, "mode_effective": "unloaded" if self.closed else self.mode}
        payload.update({"error": BUSY} if changed is None else {"mode_changed": changed, "mode_saved": changed, "message": message})
        return self.dump(payload)

    def _command(self, raw_args):
        self.read_failed = False
        parts = raw_args.split() if isinstance(raw_args, str) else []
        error = None
        if parts and parts[0] == "config":
            payload, error = self.configure(parts)
            if payload is not None:
                return self.dump(payload)
            result = self.status()
        elif parts == ["apply"]:
            result = self.status()
            if self.mode != "auto":
                error = "AUTO unavailable: apply requires effective Auto"
        elif parts == ["explain"]:
            result = self.explain()
        elif parts in (["status"], []):
            result = self.status()
        elif len(parts) == 2 and parts[0] == "mode" and parts[1] in ("off", "observe", "auto"):
            mode = parts[1]
            if self.closed:
                error = "Plugin instance unloaded; use native management and restart"
            elif mode == "auto" and not self.auto_check()["ok"]:
                error = "AUTO unavailable: " + ", ".join(self.auto_check()["reasons"])
            else:
                restoration_incomplete = False
                saved_before = self.read("mode", "off")
                try:
                    if mode != 'auto' and self.auto_failure and self.engine is None:
                        raise ValueError('Retained Auto state unavailable')
                    if mode == 'off':
                        self.ensure_retained_engine()
                    elif mode == 'observe' and self.engine is None:
                        # AUXP-04/H1: an empty Observe preview must not create durable Auto artifacts.
                        self.load_retained_state()
                    if mode != 'auto' and self.engine is not None:
                        if not self.restore_engines():
                            restoration_incomplete = True
                            raise ValueError('Auto restoration incomplete')
                        self.dispose_hooks()
                    self.ctx.set_config("mode", mode)
                except LockBusy:
                    raise
                except Exception:
                    error = ('Auto restoration incomplete' if restoration_incomplete
                             else 'Native plugin settings write failed; effective mode unchanged')
                else:
                    previous = self.mode
                    self.set_mode(mode)
                    try:
                        started = mode != "auto" or self.start_auto()
                    except LockBusy:
                        self.set_mode(previous)
                        # Revisão S1, F2: busy before Auto began; the saved mode goes back, so it matches the effective one.
                        try:
                            self.ctx.set_config("mode", saved_before if saved_before in ("off", "observe", "auto") else "off")
                        except Exception:
                            pass
                        raise
                    if not started:
                        error = "AUTO unavailable: hook registration failed"
            try:
                result = self.status()
            except LockBusy:
                # Revisão S1, F5: the change is done; say so instead of a bare busy that reads as "nothing happened".
                if error is None and not self.closed and self.mode == mode:
                    raise ModeChangedBusy(mode)
                raise
        else:
            error = USAGE
            result = self.status()
        if error:
            result.update(ok=False, error=error)
        return self.dump(result)

    @staticmethod
    def dump(payload):
        try:
            return json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
        except ValueError:
            return json.dumps({"ok": False, "error": "Result contained a non-finite number and was withheld"})
