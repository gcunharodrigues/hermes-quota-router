# decisions/aux-plan.md, AUXP-03 and D-AUXP-2: closed projection and distinct enrollment gates.
"""Synthetic auxiliary contracts; no native consumers, config or credentials."""
import copy
import unittest

from quota_router import auxiliary, mapping


class AuxiliaryGroupsTests(unittest.TestCase):
    def document(self):
        return {'model': {}, 'auxiliary': {'approval': {'provider': 'openai-codex', 'model': 'gpt-6.1-terra',
                                                       'timeout': 40, 'enabled': True, 'fallback_chain': ['synthetic']}}}

    def test_projection_target_absence_and_closed_changes(self):
        doc = self.document()
        before = copy.deepcopy(doc)
        baseline = auxiliary.project(doc, 'aux:approval')
        self.assertEqual(set(baseline), {'provider', 'model', 'base_url', 'api_mode', 'reasoning_effort'})
        self.assertEqual(baseline['reasoning_effort'], {'present': False})
        target = auxiliary.target('aux:approval', {'provider': 'anthropic', 'model': 'claude-sonnet-5-5'}, baseline)
        self.assertEqual(target['reasoning_effort'], {'present': False})
        self.assertEqual(target['base_url'], baseline['base_url'])
        self.assertEqual(target['api_mode'], baseline['api_mode'])
        updates, unset = auxiliary.changes(doc, 'aux:approval', target)
        self.assertEqual(updates, {'auxiliary.approval.provider': 'anthropic', 'auxiliary.approval.model': 'claude-sonnet-5-5'})
        self.assertEqual(set(unset), {'auxiliary.approval.base_url', 'auxiliary.approval.api_mode', 'auxiliary.approval.reasoning_effort'})
        self.assertEqual(doc, before)
        self.assertEqual(auxiliary.preconditions(doc, 'aux:approval'), [])
        # Retained groups need not occur in today's approved map.
        auxiliary.validate_projection('aux:retired_task', baseline)
        for name in ('approval', 'aux:../escape', 'aux:a.b', 'aux:', 'fallback:approval'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                auxiliary.validate_projection(name, baseline)

    def test_sensitive_fields_nulls_shapes_overlay_and_alias_rejected_without_values(self):
        secret = 'SYNTHETIC_PRIVATE_AUX_VALUE'
        for field in ('api_key', 'key_env', 'api_key_env', 'extra_body', 'base_url', 'api_mode',
                      'provider', 'model', 'reasoning_effort'):
            doc = self.document()
            doc['auxiliary']['approval'][field] = {'reasoning': secret} if field == 'extra_body' else secret
            errors = auxiliary.preconditions(doc, 'aux:approval')
            self.assertIn('auxiliary.approval.' + field, errors)
            self.assertNotIn(secret, repr(errors))
        for field in ('provider', 'model', 'base_url', 'api_mode', 'reasoning_effort'):
            doc = self.document()
            doc['auxiliary']['approval'][field] = None
            self.assertIn('auxiliary.approval.' + field, auxiliary.preconditions(doc, 'aux:approval'))
        for node, expected in (({'auxiliary': []}, 'auxiliary'), ({'auxiliary': {'approval': []}}, 'auxiliary.approval')):
            self.assertIn(expected, auxiliary.preconditions(node, 'aux:approval'))
        for value in ('runtime', {}, [], False):
            doc = self.document()
            doc['model']['openai_runtime'] = value
            self.assertIn('model.openai_runtime', auxiliary.preconditions(doc, 'aux:approval'))
        doc = self.document()
        doc['other'] = doc['auxiliary']['approval']
        self.assertIn('yaml_alias_crosses_group', auxiliary.preconditions(doc, 'aux:approval'))
        for field in ('api_key', 'key_env', 'api_key_env'):
            doc = self.document()
            doc['auxiliary']['approval'][field] = ''
            doc['auxiliary']['approval']['extra_body'] = {}
            self.assertEqual(auxiliary.preconditions(doc, 'aux:approval'), [])

    def test_enrollment_model_gate_is_not_a_restoration_precondition(self):
        doc = self.document()
        pair = mapping.approved_auxiliary()['approval']
        self.assertEqual(auxiliary.enrollment_errors(doc, 'approval', pair), [])
        doc['auxiliary']['approval']['model'] = 'gpt-manual-model'
        self.assertEqual(auxiliary.enrollment_errors(doc, 'approval', pair), ['auxiliary.approval.model'])
        self.assertEqual(auxiliary.preconditions(doc, 'aux:approval'), [])
        auxiliary.validate_projection('aux:approval', auxiliary.project(doc, 'aux:approval'))
        doc['auxiliary']['approval']['provider'] = 'auto'
        self.assertEqual(auxiliary.enrollment_errors(doc, 'approval', pair), ['auxiliary.approval.provider'])

    def test_projection_validation_is_closed_and_never_accepts_null(self):
        baseline = auxiliary.project(self.document(), 'aux:approval')
        for field in baseline:
            bad = copy.deepcopy(baseline)
            bad[field] = {'present': True, 'value': None}
            with self.subTest(field=field), self.assertRaises(ValueError):
                auxiliary.validate_projection('aux:approval', bad)
        for key, cell in (('api_key', {'present': True, 'value': 'synthetic'}),
                          ('base_url', {'present': True, 'value': 'https://custom.invalid'}),
                          ('provider', {'present': False, 'value': 'anthropic'})):
            bad = copy.deepcopy(baseline)
            bad[key] = cell
            with self.subTest(key=key), self.assertRaises(ValueError):
                auxiliary.validate_projection('aux:approval', bad)
