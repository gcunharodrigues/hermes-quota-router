# Implements decisions/hqr-20-amendment.md, section 5, AC-22 and D15/D16/D17.
"""Closed hook facts and conservative task/generation attribution (AC-22, D16, D17)."""
from datetime import datetime
from contextvars import copy_context
import hashlib
import os
from queue import Empty, Full, Queue
from threading import Thread

from .apply import durable
from .groups import target
from .settings import safe_model, safe_name, PROVIDERS

HOOKS = ('on_session_open', 'on_kanban_dispatch_tick', 'subagent_start', 'on_session_start', 'api_request_error')
TRIGGERS = HOOKS[:2]


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
        owner_context = copy_context()
        self.thread = Thread(target=owner_context.run, args=(self.run,), name='quota-router-hooks', daemon=True)
        self.thread.start()

    # decisions/s3-plan.md, "Escopo": copy closed scalar fields, never prompts/error text or blocking I/O in the callback.
    def callback(self, event):
        def receive(**kwargs):
            try:
                if self.stopped:
                    return
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
                self.queue.put_nowait(item)
            except Exception:
                return
        return receive

    def record(self, item):
        session_id = item.get('child_session_id') or item.get('session_id')
        parent = item.get('parent_session_id')
        evidence = self.evidence(session_id, parent, item['event'])
        with self.engine.locked():
            salt = self.engine.read_record('salt.json')
            if salt is None:
                salt = os.urandom(32).hex()
                self.engine.persist('salt.json', salt)
            clean = {k: v for k, v in item.items() if not k.endswith('session_id')}
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
        while True:
            item = self.queue.get()
            try:
                if item is None:
                    return
                if not self.stopped:
                    if item['event'] in TRIGGERS:
                        self.cycle()
                    else:
                        self.record(item)
            except Exception:
                # Observer failures must not reach the host or log any original payload/error text.
                pass
            finally:
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
