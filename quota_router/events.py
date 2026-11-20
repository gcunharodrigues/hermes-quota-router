# Implements decisions/hqr-20-amendment.md, section 5, AC-22 and D15/D16/D17.
"""Closed hook facts and conservative task/generation attribution (AC-22, D16, D17)."""
from datetime import datetime
from contextvars import ContextVar, copy_context
import hashlib
import os
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from time import monotonic

from .apply import FETCH_WAIT, LOCK_DEADLINE, WORKER_TRY_LOCK
from .groups import target
from .settings import safe_model, safe_name, PROVIDERS

HOOKS = ('on_session_open', 'pre_llm_call', 'on_session_start', 'pre_tool_call', 'subagent_start', 'api_request_error')
# decision D-33: decide on each prompt, at session start and before each delegation;
# the gateway tick is no longer a trigger. Each cycle runs in the caller's context, so the profile's secret scope
# (needed to read Claude's quota in a multiprofile gateway) is present.
TRIGGERS = ('on_session_open', 'pre_llm_call', 'on_session_start')
RECORDED = ('subagent_start', 'on_session_start', 'api_request_error')
DELEGATION_TOOLS = ('delegate_task',)
# Incidente 19/11: seconds the delegation hook waits for the worker's cycle before Hermes builds the child anyway.
DELEGATION_BUDGET_S = 5
WORKER_LOCK_BUDGET_S = 2
# Revisão F1–F5, R3: Hermes classifies the error (agent/turn_api_error.py) and passes `reason` and `status_code`;
# the exception class name stays an extra signal.
RATE_LIMIT_ERRORS = ('RateLimitError',)
RATE_LIMIT_REASONS = ('rate_limit', 'billing')
# Set around one cycle: the caller's context for the quota read, the providers whose reading must be refreshed,
# and the hook event that requested the cycle (recorded with its phase durations).
READER_CONTEXT = ContextVar('quota_router_reader_context', default=None)
REFRESH = ContextVar('quota_router_refresh', default=None)
TRIGGER = ContextVar('quota_router_trigger', default=None)


def run_cycle(cycle, context, refresh=None, trigger=None):
    refresh = (refresh,) if isinstance(refresh, str) else tuple(refresh or ()) or None
    tokens = (READER_CONTEXT.set(context), REFRESH.set(refresh), TRIGGER.set(trigger))
    try:
        cycle()
    finally:
        TRIGGER.reset(tokens[2])
        REFRESH.reset(tokens[1])
        READER_CONTEXT.reset(tokens[0])


def rate_limited(kwargs, error_class):
    status = kwargs.get('status_code')
    return (kwargs.get('reason') in RATE_LIMIT_REASONS or (type(status) is int and status == 429)
            or error_class in RATE_LIMIT_ERRORS)


def generation_for(history, evidence, role):
    unknown = {"state": "geração indeterminada"}
    if evidence.get('qualified') is not True:
        return unknown
    parent = evidence.get('parent_type')
    if parent == 'follow_profile_config':
        return {"state": "follow_profile_config", "reason": "segue a geração vigente por turno"}
    if parent not in ('common', 'managed', 'cron') or evidence.get('changed_after_creation') is not False:
        return unknown
    created = evidence.get('started_at')
    if isinstance(created, str):
        try:
            created = datetime.fromisoformat(created).timestamp()
        except ValueError:
            return unknown
    if type(created) not in (int, float):
        return unknown
    # decisions/hqr-20-amendment.md, D17/AC-22: any application in the 60 s safety window makes A -> B -> A indeterminate.
    if any(0 <= created - h['at'] <= 60 for h in history):
        return unknown
    earlier = [h for h in history if h['group'] == role and h['at'] < created]
    if not earlier:
        return unknown
    generation = max(earlier, key=lambda h: (h['at'], h['generation']))
    try:
        recorded = target(role, evidence['model_config'])
    except (ValueError, KeyError, TypeError):
        return unknown
    if generation['values'] != recorded:
        return unknown
    return {"state": "qualified", "generation": generation['generation'], "age_s": created - generation['at']}


def native_evidence(_session_id, _parent_session_id, _event):
    # decisions/hqr-20-amendment.md, D16/AC-22: get_session mutates token deltas and model_config has no qualified creation version.
    # Never turn a callback's currently installed generation into evidence of what a task captured.
    return {"qualified": False, "reason": "native_session_store_unqualified", "parent_type": "unknown"}


class HookWorker:
    """Bounded ephemeral queue; callbacks copy allowlisted scalars only and never wait for I/O or a cycle."""
    def __init__(self, engine, cycle, clock, evidence=None):
        self.engine, self.cycle, self.clock = engine, cycle, clock
        self.evidence = evidence or native_evidence
        self.queue = Queue(maxsize=64)
        self.stopped = False
        # Revisão F1–F5, R3: at most one queued cycle; later requests only add their refresh provider to it.
        # Each queued or running cycle carries an Event set when it ends, so a delegation can wait for it (bounded).
        self.pending = Lock()
        self.queued = None
        self.running = None
        self.refresh = set()
        owner_context = copy_context()
        self.owner_context = owner_context
        self.thread = Thread(target=owner_context.run, args=(self.run,), name='quota-router-hooks', daemon=True)
        self.thread.start()

    # decisions/s3-plan.md, "Escopo": copy closed scalar fields, never prompts/error text or blocking I/O in the callback.
    # D-33: a delegation waits for the cycle so the child is built on the new route, best effort.
    # Incidente 19/11: Hermes gives pre_tool_call 30 s, fails it closed and then suspends the callback, blocking every
    # tool for 60 s; the cycle therefore never runs in Hermes' thread, which waits at most DELEGATION_BUDGET_S for the
    # worker (joining a queued or running cycle) and then lets the child start while the worker finishes.
    def callback(self, event):
        def receive(**kwargs):
            try:
                if self.stopped:
                    return None
                if event == 'pre_tool_call':
                    if kwargs.get('tool_name') in DELEGATION_TOOLS:
                        # The cycle keeps the owner's context; only the quota read uses the caller's secret scope.
                        done = self.enqueue({"event": event, "at": self.clock().timestamp()}, copy_context(), join=True)
                        if done is not None:
                            done.wait(DELEGATION_BUDGET_S)
                    return None
                item = {"event": event, "at": self.clock().timestamp()}
                for source, name in (('provider', 'provider'), ('model', 'model'), ('child_role', 'role'), ('role', 'role')):
                    value = kwargs.get(source)
                    clean = value if name == 'provider' and value in PROVIDERS else safe_model(value) if name == 'model' else safe_name(value)
                    if clean is not None:
                        item[name] = clean
                error = kwargs.get('error')
                if isinstance(error, BaseException):
                    item['error_class'] = safe_name(type(error).__name__)
                elif isinstance(error, dict):
                    error_class = safe_name(error.get('type'))
                    if error_class is not None:
                        item['error_class'] = error_class
                for key in ('session_id', 'child_session_id', 'parent_session_id'):
                    value = kwargs.get(key)
                    if isinstance(value, str) and len(value) <= 256:
                        # Raw ids live only in this bounded, in-memory queue until native evidence is read.
                        item[key] = value
                limited = event == 'api_request_error' and rate_limited(kwargs, item.get('error_class'))
                if event in TRIGGERS or limited:
                    # The caller's context carries the profile secret scope into the worker's cycle.
                    self.enqueue(item, copy_context(), item.get('provider') if limited else None)
                elif event in RECORDED:
                    self.queue.put_nowait(item)
            except Exception:
                return None
            return None
        return receive

    def enqueue(self, item, context, refresh=None, join=False):
        """Queue a cycle request, coalesced into the one already queued (R3); a recorded fact is queued anyway.

        Returns the Event of the cycle that will serve the request; with `join`, a running cycle serves it too.
        """
        with self.pending:
            if refresh in PROVIDERS:
                self.refresh.add(refresh)
            if join and self.queued is None and self.running is not None:
                return self.running
            cycle = self.queued is None
            if cycle:
                self.queued = Event()
            done = self.queued
        if cycle:
            item['context'] = context
        elif item['event'] not in RECORDED:
            return done
        try:
            self.queue.put_nowait(item)
        except Full:
            if cycle:
                with self.pending:
                    self.queued = None
                done.set()
        return done

    def record(self, item):
        session_id = item.get('child_session_id') or item.get('session_id')
        parent = item.get('parent_session_id')
        evidence = self.evidence(session_id, parent, item['event'])
        with self.engine.locked():
            salt = self.engine.read_record('salt.json')
            if salt is None:
                salt = os.urandom(32).hex()
                self.engine.persist('salt.json', salt)
            clean = {k: v for k, v in item.items() if not k.endswith('session_id') and k not in ('context', 'refresh')}
            # decisions/s3-plan.md, "Escopo": persist session identifiers only as locally salted hashes.
            for key in ('session_id', 'child_session_id', 'parent_session_id'):
                if key in item:
                    clean[key + '_hash'] = hashlib.sha256((salt + item[key]).encode()).hexdigest()
            role = item.get('role') or 'conversation'
            clean['decision'] = generation_for(self.engine.state['history'], evidence, role)
            records = self.engine.read_record('events.json', [])
            records.append(clean)
            self.engine.persist('events.json', records[-128:])

    def run(self):
        # A worker created by a command must not inherit that command's fetch budget.
        WORKER_TRY_LOCK.set(True)
        FETCH_WAIT.set(None)
        while True:
            item = self.queue.get()
            deadline = LOCK_DEADLINE.set(monotonic() + WORKER_LOCK_BUDGET_S)
            try:
                if item is None:
                    return
                if not self.stopped:
                    context = item.get('context')
                    if context is not None:
                        with self.pending:
                            self.running, self.queued = self.queued, None
                            refresh, self.refresh = tuple(sorted(self.refresh)), set()
                        try:
                            run_cycle(self.cycle, context, refresh, item['event'])
                        finally:
                            with self.pending:
                                done, self.running = self.running, None
                            if done is not None:
                                done.set()
                    if item['event'] in RECORDED:
                        self.record(item)
            except Exception:
                # Observer failures must not reach the host or log any original payload/error text.
                pass
            finally:
                LOCK_DEADLINE.reset(deadline)
                self.queue.task_done()

    def wait(self):
        self.queue.join()

    def close(self):
        self.stopped = True
        try:
            self.queue.put_nowait(None)
        except Full:
            # Free one queued fact; unload must never block on the queue.
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except Empty:
                pass
            try:
                self.queue.put_nowait(None)
            except Full:
                pass
