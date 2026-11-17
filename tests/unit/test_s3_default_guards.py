# Regression contract: decisions/hqr-20-amendment.md, D18/R1: guards and imported route bindings.
import unittest

from quota_router import compat


class DefaultGuardCoverageTests(unittest.TestCase):
    def test_canonical_provider_guards_and_live_import_bindings_are_required(self):
        required = {
            'hermes_cli.runtime_provider': ('expand_direct_api_alias', '_resolve_named_custom_runtime',
                '_get_named_custom_provider', 'resolve_codex_runtime_credentials', 'resolve_provider', '_resolves_to_custom'),
            'hermes_cli.runtime_provider_custom': ('expand_direct_api_alias', '_resolve_named_custom_runtime',
                '_get_named_custom_provider', '_select_named_custom_provider', '_shadowed_by_builtin',
                '_normalize_custom_provider_name', '_rp'),
            'hermes_cli.models': ('opencode_provider_family',),
            'utils': ('base_url_host_matches', 'base_url_hostname', 'base_url_path'),
        }
        for module, names in required.items():
            with self.subTest(module=module):
                self.assertTrue(set(names) <= set(compat.FUNCTIONS.get(module, ())), module)
        required_constants = {
            'hermes_cli.runtime_provider': ('_HOST_MANDATED_API_MODES',),
            'hermes_cli.runtime_provider_custom': ('_DIRECT_API_BASE_URLS',),
            'hermes_cli.providers': ('_RESPONSES_NATIVE_HOSTS',),
        }
        for module, names in required_constants.items():
            with self.subTest(module=module):
                self.assertTrue(set(names) <= set(compat.CONSTANTS.get(module, ())), module)
