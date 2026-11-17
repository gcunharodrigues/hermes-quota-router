# Regression contract: decisions/hqr-20-amendment.md, D18; native route defaults and exact recovery.
import copy
import json
from pathlib import Path
import tempfile
import unittest

from quota_router import groups, compat
from quota_router.apply import Engine
from s3_fakes import Backend, TARGET, qualified
import test_s3_lifecycle as fixtures
from s2_fakes import codex, claude, reader_for

# Public native constants, not an account or profile snapshot.
ROUTES = {'openai-codex': ('https://chatgpt.com/backend-api/codex', 'codex_responses'),
          'anthropic': ('https://api.anthropic.com', 'anthropic_messages')}


def native_shape(backend, provider='openai-codex'):
    url, mode = ROUTES[provider]
    backend.document['model'].update(provider=provider, base_url=url, api_mode=mode)
    node = backend.document['delegation']['backends']['model_map']['options'][0]
    node.update(provider=provider, base_url=url, api_mode=mode)


class NativeDefaultTests(unittest.TestCase):
    def test_current_provider_defaults_are_accepted_but_custom_and_cross_provider_are_not(self):
        for provider in ROUTES:
            backend = Backend()
            native_shape(backend, provider)
            for role, prefix in [('conversation', 'model.'), ('general', groups.OPTIONS + '.')]:
                with self.subTest(provider=provider, role=role):
                    self.assertEqual(groups.preconditions(backend.read(), role), [])
                    for field, bad in [('base_url', 'https://synthetic.invalid/private'), ('api_mode', 'private_mode'),
                                       ('base_url', ROUTES['anthropic' if provider == 'openai-codex' else 'openai-codex'][0])]:
                        document = backend.read()
                        node = document['model'] if role == 'conversation' else document['delegation']['backends']['model_map']['options'][0]
                        node[field] = bad
                        errors = groups.preconditions(document, role)
                        self.assertIn(prefix + field, errors)
                        self.assertNotIn(bad, repr(errors))

    def test_target_syncs_native_default_fields_for_both_providers_and_roles(self):
        for provider, (url, mode) in ROUTES.items():
            for role in ('conversation', 'general'):
                with self.subTest(provider=provider, role=role):
                    target = groups.target(role, dict(TARGET, provider=provider))
                    keys = groups.CONVERSATION if role == 'conversation' else groups.FIELDS
                    self.assertEqual(target[keys[2]], {'present': True, 'value': url})
                    self.assertEqual(target[keys[3]], {'present': True, 'value': mode})
                    self.assertEqual(groups.validate_projection(role, target), target)
                    target[keys[2]]['value'] = 'https://synthetic.invalid/private'
                    with self.assertRaises(ValueError):
                        groups.validate_projection(role, target)

    def test_apply_off_and_reload_restore_original_presence_and_native_defaults(self):
        for provider in ROUTES:
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as root:
                backend = Backend()
                native_shape(backend, provider)
                baseline = backend.read()
                engine = Engine(root, backend, qualified)
                other = 'anthropic' if provider == 'openai-codex' else 'openai-codex'
                engine.cycle({role: dict(TARGET, provider=other) for role in ('conversation', 'general')}, now=10)
                self.assertEqual(set(engine.report(10)['groups_out']), set())
                self.assertEqual(backend.read()['model']['provider'], other)
                reloaded = Engine(root, backend, qualified)
                self.assertTrue(reloaded.restore(20))
                self.assertEqual(backend.read(), baseline)

    def test_every_interrupted_field_recovers_native_route_mixtures_and_restores(self):
        class Interrupted(Exception):
            pass
        class Partial(Backend):
            def write(self, updates, unset):
                if self.remaining is None:
                    return super().write(updates, unset)
                # Native conversation updates can be interrupted between any projected fields.
                for key, value in updates.items():
                    super().write({key: value}, ())
                    self.remaining -= 1
                    if self.remaining == 0:
                        self.remaining = None
                        raise Interrupted()
        for restoring in (False, True):
            for count in range(1, 6):
                with self.subTest(restoring=restoring, count=count), tempfile.TemporaryDirectory() as root:
                    backend = Partial()
                    backend.remaining = None
                    native_shape(backend)
                    baseline = backend.read()
                    engine = Engine(root, backend, qualified)
                    if restoring:
                        engine.cycle({'conversation': TARGET}, now=10)
                    prior = backend.read()
                    backend.remaining = count
                    with self.assertRaises(Interrupted):
                        engine.restore(20) if restoring else engine.cycle({'conversation': TARGET}, now=10)
                    journal = engine.read_record('journal.json')
                    unchanged = backend.read() == (baseline if not restoring else prior)
                    reloaded = Engine(root, backend, qualified)
                    self.assertTrue(reloaded.recover())
                    self.assertEqual(reloaded.report(20)['groups_out'], {})
                    expected = journal['prior'] if unchanged else journal['target']
                    self.assertEqual(groups.project(backend.read(), 'conversation'), expected)
                    self.assertTrue(reloaded.restore(30))
                    self.assertEqual(backend.read(), baseline)

    def test_custom_endpoint_after_journal_is_never_recovered_or_restored(self):
        def interrupt(point):
            if point == 'journal':
                raise RuntimeError('synthetic interruption')
        with tempfile.TemporaryDirectory() as root:
            backend = Backend()
            native_shape(backend)
            engine = Engine(root, backend, qualified, interrupt)
            with self.assertRaises(RuntimeError):
                engine.cycle({'conversation': TARGET}, now=10)
            backend.document['model']['base_url'] = 'https://synthetic.invalid/private'
            before = backend.read()
            reloaded = Engine(root, backend, qualified)
            self.assertTrue(reloaded.recover())
            self.assertTrue(reloaded.restore(20))
            self.assertEqual(backend.read(), before)
            self.assertEqual(reloaded.report(20)['groups_out']['conversation'], ['model.base_url'])
            self.assertNotIn('synthetic.invalid', ''.join(p.read_text() for p in Path(root).glob('*.json')))

    def test_native_default_sources_are_part_of_the_required_fingerprint_set(self):
        constants = {m + '.' + n for m, names in compat.CONSTANTS.items() for n in names}
        self.assertTrue({'hermes_cli.auth_constants.DEFAULT_CODEX_BASE_URL',
                         'hermes_cli.runtime_provider._ANTHROPIC_DEFAULT_BASE_URL',
                         'hermes_cli.providers.TRANSPORT_TO_API_MODE'} <= constants)
        functions = {m + '.' + n for m, names in compat.FUNCTIONS.items() for n in names}
        self.assertTrue({'hermes_cli.runtime_provider._explicit_codex',
                         'hermes_cli.runtime_provider._explicit_anthropic'} <= functions)

    def test_native_route_writes_keep_observe_auto_hysteresis_continuity(self):
        helper = fixtures.AutoCommandTests()
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend = helper.manager(root)
            self.addCleanup(manager.close)
            native_shape(backend)
            baseline = backend.read()
            usage = {'openai_codex': codex(30, week_reset_h=84), 'anthropic': claude(10, week_reset_h=84)}
            manager.importer = lambda: reader_for(**usage)
            helper.call(manager, 'config approve-map base')
            helper.call(manager, 'mode observe')
            usage['openai_codex'] = codex(5, week_reset_h=84)
            manager.cache.clear()
            self.assertEqual(helper.call(manager, 'explain')['decisions']['routes']['general']['choice'], 'anthropic')
            helper.call(manager, 'mode auto')
            self.assertEqual(groups.option(backend.read(), 'general')['provider'], 'anthropic')
            for _ in range(3):
                manager.cache.clear()
                self.assertEqual(helper.call(manager, 'apply')['decisions']['routes']['general']['choice'], 'anthropic')
            self.assertTrue(helper.call(manager, 'mode off')['ok'])
            self.assertEqual(backend.read(), baseline)
