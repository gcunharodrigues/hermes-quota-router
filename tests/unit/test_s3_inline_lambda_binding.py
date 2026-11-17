# Regression contract: decisions/hqr-20-amendment.md, D18/R1; review R3 (loaded inline lambda).
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from quota_router import compat

RUNTIME = 'hermes_cli.runtime_provider'
NAME = '_OAUTH_RUNTIME_PROVIDERS'
SOURCE = '''
_OAUTH_RUNTIME_PROVIDERS = {
    "openai-codex": _OAuthRuntimeSpec(lambda: resolve_codex_runtime_credentials(), "codex_responses", "hermes-auth-store",
                                      "last_refresh", "unavailable"),
}
'''


class InlineLambdaBindingTests(unittest.TestCase):
    def fixture(self, root, source=SOURCE):
        path = root / 'hermes_cli/runtime_provider.py'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
        module = types.ModuleType(RUNTIME)
        module.__file__ = str(path)
        module.__dict__['_OAuthRuntimeSpec'] = lambda resolve, api_mode, *args: types.SimpleNamespace(
            resolve=resolve, api_mode=api_mode, default_base_url='')
        module.__dict__['resolve_codex_runtime_credentials'] = mock.Mock(side_effect=AssertionError('resolver must not run'))
        # Only a synthetic fixture is executed; no native module is imported or evaluated.
        exec(compile(source, str(path), 'exec'), module.__dict__)
        return module, path

    def test_native_shaped_loaded_inline_lambda_matches_inert_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module, path = self.fixture(root)
            specs = {RUNTIME: (NAME,)}
            expected = compat.collect_symbols(root, specs={}, constant_specs=specs)
            self.assertIsNotNone(expected['constants'][RUNTIME + '.' + NAME])
            with mock.patch.dict(sys.modules, {RUNTIME: module}):
                actual = compat.collect_symbols(root, specs={}, constant_specs=specs)
            self.assertEqual(actual, expected)
            module.resolve_codex_runtime_credentials.assert_not_called()

    def test_loaded_inline_resolver_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module, path = self.fixture(root)
            module.__dict__[NAME]['openai-codex'].resolve = lambda: module.resolve_codex_runtime_credentials()
            with mock.patch.dict(sys.modules, {RUNTIME: module}):
                actual = compat.collect_symbols(root, specs={}, constant_specs={RUNTIME: (NAME,)})
            self.assertIsNone(actual['constants'][RUNTIME + '.' + NAME])

    def test_two_lambdas_on_one_source_line_are_not_guessed(self):
        # Both resolvers are direct lambdas in valid dispatch entries on the same physical line.
        source = SOURCE.replace('"hermes-auth-store",\n                                      "last_refresh", "unavailable"),',
                                '"hermes-auth-store", "last_refresh", "unavailable"), '
                                '"unrelated": _OAuthRuntimeSpec(lambda: forbidden(), "other", "source", "expiry", "unavailable"),')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module, path = self.fixture(root, source)
            specs = {RUNTIME: (NAME,)}
            inert = compat.collect_symbols(root, specs={}, constant_specs=specs)
            self.assertIsNotNone(inert['constants'][RUNTIME + '.' + NAME], 'dispatch source must be accepted before testing ambiguity')
            with mock.patch.dict(sys.modules, {RUNTIME: module}):
                actual = compat.collect_symbols(root, specs={}, constant_specs=specs)
            self.assertIsNone(actual['constants'][RUNTIME + '.' + NAME])
            module.resolve_codex_runtime_credentials.assert_not_called()
