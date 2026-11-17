"""SOL-04 pure downgrade preparation, not a persisted migration or permission to replace any state."""
import ast
import copy
from pathlib import Path
import subprocess
import types
import unittest

from s3_fakes import CONFIG
from quota_router import groups
from quota_router.apply import Engine

OLD = '233f4beae8fa0e089f95a8c6ef3cee1ba0b7ff8a'
ARCHIVE = 'hqr38_downgrade_archive'


def old_validator():
    root = Path(__file__).resolve().parents[2]
    def source(path):
        return subprocess.check_output(['git', '-C', str(root), 'show', OLD + ':' + path], text=True)
    old_groups = types.ModuleType('pure_old_groups')
    old_groups.__package__ = 'quota_router'
    exec(compile(source('quota_router/groups.py'), OLD + ':groups.py', 'exec'), old_groups.__dict__)
    engine = next(node for node in ast.parse(source('quota_router/apply.py')).body
                  if isinstance(node, ast.ClassDef) and node.name == 'Engine')
    validator = next(node for node in engine.body if isinstance(node, ast.FunctionDef) and node.name == 'validate_state')
    validator.decorator_list = []
    namespace = {'groups': old_groups}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[validator], type_ignores=[])), OLD + ':validate_state', 'exec'), namespace)
    return namespace['validate_state']


def off_state():
    state = {'schema': 1, 'groups': {}, 'history': [], 'generation': 2, 'auto_declared': False, 'last_cycle': 20}
    for role in ('conversation', 'fallback:conversation'):
        projection = groups.project(copy.deepcopy(CONFIG), role)
        state['groups'][role] = {'baseline': copy.deepcopy(projection), 'last': copy.deepcopy(projection), 'active': False, 'restored': True}
        state['history'].append({'generation': len(state['history']) + 1, 'at': 10, 'group': role, 'values': projection})
    return state


class DowngradePreparationTests(unittest.TestCase):
    def prepare(self, state, **kwargs):
        from quota_router.downgrade import prepare_legacy_state
        return prepare_legacy_state(state, mode=kwargs.get('mode', 'off'), journal=kwargs.get('journal'))

    def test_off_alone_really_is_not_accepted_by_old_validator(self):
        state = off_state()
        Engine.validate_state(state)
        with self.assertRaises(ValueError):
            old_validator()(state)

    def test_prepared_state_is_accepted_by_both_and_retains_exact_full_source(self):
        state = off_state()
        before = copy.deepcopy(state)
        prepared = self.prepare(state)
        self.assertEqual(state, before)
        old_validator()(prepared)
        Engine.validate_state(prepared)
        self.assertEqual(prepared[ARCHIVE]['source_state'], state)
        self.assertEqual(prepared[ARCHIVE]['rollback'], OLD)
        self.assertEqual(prepared['generation'], state['generation'])
        self.assertFalse(prepared['auto_declared'])
        self.assertEqual(prepared['groups'], {'conversation': state['groups']['conversation']})
        self.assertEqual(prepared['history'], [state['history'][0]])

    def test_preparation_refuses_active_auto_pending_journal_or_nonoff_mode(self):
        for case in ('active', 'declared', 'journal', 'mode'):
            with self.subTest(case=case):
                state = off_state()
                kwargs = {}
                if case == 'active':
                    state['groups']['fallback:conversation']['active'] = True
                elif case == 'declared':
                    state['auto_declared'] = True
                elif case == 'journal':
                    kwargs['journal'] = {}  # even an empty but present journal is not confirmed absence.
                else:
                    kwargs['mode'] = 'observe'
                with self.assertRaises(ValueError):
                    self.prepare(state, **kwargs)

    def test_incomplete_restoration_without_exclusion_is_not_off_evidence(self):
        state = off_state()
        entry = state['groups']['fallback:conversation']
        entry['restored'] = False
        entry['last'] = groups.target('fallback:conversation', {'chain': [{'provider': 'anthropic', 'model': 'claude-opus-5-5'}]})
        with self.assertRaises(ValueError):
            self.prepare(state)

    def test_excluded_human_edit_is_archived_not_overwritten_or_reenrolled(self):
        state = off_state()
        entry = state['groups']['fallback:conversation']
        entry.update(restored=False, excluded=['fallback_providers'])
        prepared = self.prepare(state)
        self.assertEqual(prepared[ARCHIVE]['source_state']['groups']['fallback:conversation'], entry)
        self.assertNotIn('fallback:conversation', prepared['groups'])
        with self.assertRaises(ValueError):
            self.prepare(prepared)  # do not nest or overwrite a prior archive.
