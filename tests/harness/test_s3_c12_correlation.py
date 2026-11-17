"""Execute the installed C12 function with disposable storage and real redaction, never a native host."""
import ast
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

from quota_router.apply import Engine
from quota_router.events import HookWorker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'installed'))
NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)


class C12CorrelationTests(unittest.TestCase):
    @contextmanager
    def proof(self, history=1, delivery='current'):
        runner = importlib.import_module('s3_auto')
        functions: list[ast.stmt] = [node for node in ast.parse(runner.EXERCISE).body if isinstance(node, ast.FunctionDef) and node.name == 'quota_error']
        self.assertEqual(len(functions), 1)
        with tempfile.TemporaryDirectory() as root:
            engine = Engine(root, None, lambda: {'ok': True})
            worker = HookWorker(engine, lambda: None, lambda: NOW)
            calls = []
            def invoke(event, **payload):
                self.assertEqual(event, 'api_request_error')
                calls.append(payload)
                if delivery == 'inert':
                    return
                if delivery == 'wrong_session':
                    payload = dict(payload, session_id='another-current-session')
                if delivery == 'stale':
                    worker.clock = lambda: NOW - timedelta(seconds=1)
                worker.callback(event)(**payload)
            def function(module, name):
                self.assertEqual((module, name), ('hermes_cli.plugins', 'invoke_hook'))
                return invoke
            manager = SimpleNamespace(engine=engine, clock=lambda: NOW, wait_hooks=worker.wait)
            namespace = {'manager': manager, 'consumers': SimpleNamespace(native=SimpleNamespace(function=function)),
                         'json': json, 'hashlib': hashlib, 'command': lambda _: {'coverage': {'hooks': 'unqualified_until_installed_run'}}}
            try:
                for index in range(history):
                    worker.record({'event': 'api_request_error', 'at': NOW.timestamp() - 100,
                                   'provider': 'anthropic', 'model': 'claude-opus-5-5', 'error_class': 'QuotaExhausted',
                                   'session_id': 'synthetic-quota-task' if index == 0 else f'old-session-{index}'})
                exec(compile(ast.Module(body=functions, type_ignores=[]), '<installed-c12-only>', 'exec'), namespace)
                yield namespace['quota_error'], engine, calls
            finally:
                worker.wait()
                worker.close()
                worker.thread.join(2)
                self.assertFalse(worker.thread.is_alive())

    def test_old_history_cannot_prove_an_inert_current_delivery(self):
        for history in (1, 128):
            with self.subTest(history=history), self.proof(history, 'inert') as (proof, engine, calls):
                before = engine.read_record('events.json', [])
                with self.assertRaises(AssertionError):
                    proof()
                self.assertEqual(len(calls), 1)
                self.assertEqual(engine.read_record('events.json', []), before)

    def test_new_redacted_record_proves_the_current_emission_even_at_retention_limit(self):
        for history in (0, 1, 128):
            with self.subTest(history=history), self.proof(history) as (proof, engine, calls):
                result = proof()
                current_id = calls[0]['session_id']
                expected = hashlib.sha256((engine.read_record('salt.json') + current_id).encode()).hexdigest()
                self.assertTrue(result.get('recorded'))
                self.assertEqual(result.get('session_id_hash'), expected)
                self.assertEqual(result.get('emitted_at'), NOW.timestamp())
                self.assertEqual(result.get('recorded_at'), NOW.timestamp())
                records = engine.read_record('events.json', []) or []
                self.assertEqual(records[-1]['session_id_hash'], expected)
                self.assertNotIn(current_id, json.dumps(records))
                self.assertNotIn('SYNTHETIC_PRIVATE_ERROR', json.dumps(records))

    def test_each_emission_has_its_own_correlation(self):
        with self.proof() as (proof, engine, calls):
            first = proof()
            second = proof()
            self.assertNotEqual(calls[0]['session_id'], calls[1]['session_id'])
            self.assertNotEqual(first.get('session_id_hash'), second.get('session_id_hash'))

    def test_unrelated_new_record_cannot_satisfy_current_correlation(self):
        with self.proof(delivery='wrong_session') as (proof, engine, calls):
            with self.assertRaises(AssertionError):
                proof()
            self.assertEqual(len(engine.read_record('events.json', []) or []), 2)

    def test_new_correlated_record_before_the_emission_watermark_is_rejected(self):
        with self.proof(delivery='stale') as (proof, engine, calls):
            with self.assertRaises(AssertionError):
                proof()
            self.assertEqual(len(engine.read_record('events.json', []) or []), 2)
