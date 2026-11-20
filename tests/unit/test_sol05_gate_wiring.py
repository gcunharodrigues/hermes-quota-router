"""SOL-05 static wiring checks only; do not execute the blocked persistent transactions."""
import ast
from pathlib import Path
import unittest


class EffectiveGateWiringTests(unittest.TestCase):
    def test_cycle_and_write_use_effective_chain_guard(self):
        source = (Path(__file__).resolve().parents[2] / 'quota_router' / 'apply.py').read_text()
        engine = next(node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == 'Engine')
        for name in ('cycle_locked', 'write'):
            with self.subTest(name=name):
                method = next(node for node in engine.body if isinstance(node, ast.FunctionDef) and node.name == name)
                calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
                self.assertTrue(any(isinstance(node.func, ast.Attribute) and node.func.attr == 'effective_fallback_errors'
                                    for node in calls), name)
