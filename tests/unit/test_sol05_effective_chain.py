"""SOL-05: qualify the effective native chain without modifying human inheritance or legacy keys."""
import copy
import unittest

from s3_fakes import CONFIG
from quota_router import groups

SOL = {'provider': 'openai-codex', 'model': 'gpt-6.1-sol'}
OPUS = {'provider': 'anthropic', 'model': 'claude-opus-5-5'}


class EffectiveChainTests(unittest.TestCase):
    def errors(self, document, role, chain, baseline=None):
        projection = groups.target(role, {'chain': chain}, baseline=baseline)
        return groups.effective_fallback_errors(document, role, projection, chain)

    def test_absent_route_key_does_not_mean_empty_effective_chain(self):
        document = copy.deepcopy(CONFIG)
        document['delegation']['fallback_providers'] = [OPUS]
        before = copy.deepcopy(document)
        self.assertEqual(self.errors(document, 'fallback:general', []), ['delegation.fallback_providers'])
        self.assertEqual(document, before)

    def test_explicit_empty_route_key_suppresses_inheritance(self):
        document = copy.deepcopy(CONFIG)
        document['delegation']['fallback_providers'] = [OPUS]
        baseline = {'fallback_providers': {'present': True, 'value': []}}
        self.assertEqual(self.errors(document, 'fallback:general', [], baseline), [])

    def test_declared_chain_prevents_unqualified_inheritance_from_affecting_route(self):
        document = copy.deepcopy(CONFIG)
        document['delegation']['fallback_providers'] = [{'provider': 'custom', 'model': 'PRIVATE'}]
        self.assertEqual(self.errors(document, 'fallback:general', [SOL]), [])

    def test_legacy_is_appended_even_over_explicit_empty_and_is_not_edited(self):
        document = copy.deepcopy(CONFIG)
        document['fallback_model'] = OPUS
        before = copy.deepcopy(document)
        baseline = {'fallback_providers': {'present': True, 'value': []}}
        self.assertEqual(self.errors(document, 'fallback:conversation', [], baseline), ['fallback_model'])
        self.assertEqual(document, before)

    def test_eligible_duplicate_legacy_is_qualified_without_becoming_owned(self):
        document = copy.deepcopy(CONFIG)
        document['fallback_model'] = OPUS
        self.assertEqual(self.errors(document, 'fallback:conversation', [SOL, OPUS]), [])

    def test_wrong_model_or_private_legacy_cannot_enter_effective_chain(self):
        for entry in (dict(OPUS, model='claude-sonnet-5-5'), dict(OPUS, api_key='PRIVATE_SYNTHETIC'), 'UNQUALIFIED'):
            with self.subTest(entry=entry):
                document = copy.deepcopy(CONFIG)
                document['fallback_model'] = entry
                self.assertEqual(self.errors(document, 'fallback:conversation', [SOL]), ['fallback_model'])

    def test_legacy_does_not_leak_into_explicit_pinned_delegation_chain(self):
        document = copy.deepcopy(CONFIG)
        document['fallback_model'] = OPUS
        self.assertEqual(self.errors(document, 'fallback:general', [SOL]), [])
