# Contract: decisions/aux-plan.md, "Configuração consumers.auxiliary", D-AUXP-7/8 and AC-24.
"""Auxiliary settings validate independently without weakening approved role contracts."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from quota_router.mapping import approved_auxiliary
from quota_router.render import SETTINGS_TEXT, render
from quota_router.settings import DEFAULTS, load, validate


class AuxiliarySettingsTests(unittest.TestCase):
    def test_defaults_schema_render_and_boolean_validation_are_consistent(self):
        self.assertIn('consumers.auxiliary', DEFAULTS)
        self.assertIs(DEFAULTS['consumers.auxiliary'], False)
        self.assertEqual(DEFAULTS['auxiliary_map'], {})
        for value, expected in ((True, True), (False, False), ('true', True), ('false', False)):
            self.assertEqual(validate('consumers.auxiliary', value), (True, expected))
        self.assertFalse(validate('consumers.auxiliary', 'invalid')[0])
        schema = json.loads((Path(__file__).resolve().parents[2] / 'plugin.yaml').read_text())['config_schema']
        self.assertEqual(schema['consumers.auxiliary']['default'], False)
        self.assertEqual(schema['consumers.auxiliary']['type'], 'bool')
        self.assertEqual(schema['auxiliary_map']['default'], {})
        self.assertEqual(schema['auxiliary_map']['type'], 'dict')
        self.assertIn('consumers.auxiliary', SETTINGS_TEXT)
        self.assertIn('auxiliary_map', SETTINGS_TEXT)
        settings, invalid = load(lambda key, default: default)
        text = render('config', {'settings': settings, 'settings_invalid': invalid})
        self.assertIn('`consumers.auxiliary` = desligado', text)
        self.assertIn('`auxiliary_map` = não aprovado', text)
        self.assertIn('/quota-router config approve-map auxiliary', text)

    def test_map_validation_preserves_absent_effort_only_for_claude_approval(self):
        good = approved_auxiliary()
        self.assertEqual(validate('auxiliary_map', good), (True, good))
        self.assertEqual(validate('auxiliary_map', {}), (True, {}))
        self.assertFalse(validate('roles', good)[0], 'Role validation must still require effort')
        mutations = []
        for task, provider, key, value in (
            ('approval', 'anthropic', 'effort', None),
            ('approval', 'anthropic', 'effort', 'none'),
            ('approval', 'anthropic', 'effort', []),
            ('approval', 'openai-codex', 'model', 'claude-sonnet-5-5'),
            ('compression', 'anthropic', 'model', 'gpt-6.1-terra'),
            ('compression', 'anthropic', 'effort', 'ultra'),
            ('compression', 'anthropic', 'api_key', 'SYNTHETIC_PRIVATE_VALUE'),
        ):
            bad = deepcopy(good)
            bad[task][provider][key] = value
            mutations.append(bad)
        for task, provider in (('approval', 'openai-codex'), ('compression', 'anthropic')):
            bad = deepcopy(good)
            del bad[task][provider]['effort']
            mutations.append(bad)
        mutations.extend([[], None, {'unsafe.task/path': good['compression']}, {'cron': {'follows': 'conversation'}},
                          {'compression': {'anthropic': good['compression']['anthropic']}}, {'compression': []}])
        for bad in mutations:
            with self.subTest(index=mutations.index(bad)):
                ok, reason = validate('auxiliary_map', bad)
                self.assertFalse(ok)
                self.assertIsInstance(reason, str)
                self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', reason)
        saved = {'auxiliary_map': {'private': 'SYNTHETIC_PRIVATE_VALUE'}, 'consumers.auxiliary': 'SYNTHETIC_PRIVATE_VALUE'}
        effective, invalid = load(lambda key, default: saved.get(key, default))
        self.assertEqual(effective['auxiliary_map'], {})
        self.assertIs(effective['consumers.auxiliary'], False)
        self.assertEqual(set(invalid), set(saved))
        self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', repr(invalid))
