# Contract: decisions/aux-plan.md, D-AUXP-8, "Configuração consumers.auxiliary", H4 and AC-24.
"""Exercise actual management commands over disposable settings and synthetic native dependencies."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from quota_router.lifecycle import Management
from quota_router.mapping import approved_auxiliary, approved_base
from s2_fakes import NOW, claude, codex, reader_for
from s3_fakes import Backend, qualified
from test_s3_lifecycle import AutoContext


class AuxiliaryCommandTests(unittest.TestCase):
    def manager(self, root, ctx=None, sources=None):
        ctx = ctx or AutoContext()
        backend = Backend()
        reader = reader_for(openai_codex=codex(100), anthropic=claude(10))
        manager = Management(ctx, importer=lambda: reader, sources=sources or (lambda: (backend.read(), [])),
                             clock=lambda: NOW, profile=lambda: 'default', backend=backend, data_dir=root,
                             compatible=qualified, catalogs=lambda: {})
        self.addCleanup(manager.close)
        return manager, ctx, backend, reader

    def call(self, manager, command):
        return json.loads(manager.command(command + ' --json'))

    def test_approve_auxiliary_persists_only_auxiliary_map_without_inventory_or_quota(self):
        def unavailable():
            raise AssertionError('Approving the static auxiliary map must not read the native inventory')

        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend, reader = self.manager(root, sources=unavailable)
            before = backend.read()
            result = self.call(manager, 'config approve-map auxiliary')
            self.assertTrue(result['ok'], result)
            self.assertEqual(ctx.writes, [('auxiliary_map', approved_auxiliary())])
            self.assertEqual(result['changed'], {'auxiliary_map': approved_auxiliary()})
            self.assertFalse(result['settings']['consumers.auxiliary'])
            self.assertEqual(result['settings']['roles'], {})
            self.assertEqual(reader.calls, [])
            self.assertEqual(backend.writes, [])
            self.assertEqual(backend.read(), before)
            self.assertEqual(list(Path(root).iterdir()), [])
            self.assertIsNone(manager.engine)
            self.assertIn('aprovado para 11 tarefas', manager.command('config show'))

    def test_approved_map_survives_reload_and_set_reset_do_not_enable_routing(self):
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend, _ = self.manager(root)
            approved = self.call(manager, 'config approve-map auxiliary')
            self.assertTrue(approved['ok'], approved)
            saved = deepcopy(ctx.settings['auxiliary_map'])
            saved['compression']['openai-codex']['effort'] = 'high'
            ctx.settings['auxiliary_map'] = deepcopy(saved)
            reloaded, _, _, _ = self.manager(root, ctx)
            self.assertEqual(self.call(reloaded, 'config show')['settings']['auxiliary_map'], saved)
            self.assertTrue(self.call(reloaded, 'config set consumers.auxiliary true')['ok'])
            self.assertTrue(ctx.settings['consumers.auxiliary'])
            self.assertEqual(ctx.settings['auxiliary_map'], saved)
            count = len(ctx.writes)
            invalid = self.call(reloaded, 'config set consumers.auxiliary invalid')
            self.assertFalse(invalid['ok'])
            self.assertEqual(len(ctx.writes), count)
            self.assertTrue(self.call(reloaded, 'config reset consumers.auxiliary')['ok'])
            self.assertFalse(ctx.settings['consumers.auxiliary'])
            self.assertTrue(self.call(reloaded, 'config reset auxiliary_map')['ok'])
            self.assertEqual(ctx.settings['auxiliary_map'], {})
            self.assertEqual(backend.writes, [])
            self.assertEqual(ctx.settings.get('mode', 'off'), 'off')

    def test_invalid_saved_auxiliary_settings_suspend_all_auto_without_echo(self):
        for key in ('auxiliary_map', 'consumers.auxiliary'):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as root:
                manager, ctx, backend, _ = self.manager(root)
                self.assertTrue(self.call(manager, 'config approve-map base')['ok'])
                self.assertTrue(self.call(manager, 'mode auto')['ok'])
                before, writes = backend.read(), len(backend.writes)
                ctx.settings[key] = 'SYNTHETIC_PRIVATE_VALUE'
                result = self.call(manager, 'apply')
                self.assertFalse(result['auto_available'])
                self.assertIn(key, result['settings_invalid'])
                self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', json.dumps(result))
                self.assertEqual(len(backend.writes), writes)
                self.assertEqual(backend.read(), before)
                manager.close()

    def test_auxiliary_approval_preserves_base_map_and_default_off_leaves_auxiliary_pins_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            manager, ctx, backend, _ = self.manager(root)
            pins = {task: {'provider': 'openai-codex', 'model': row['openai-codex']['model'],
                           'reasoning_effort': row['openai-codex']['effort']} for task, row in approved_auxiliary().items()}
            del pins['voice_chat']['reasoning_effort']
            pins['background_review']['enabled'] = True
            backend.document['auxiliary'] = deepcopy(pins)
            backend.document['image_gen'] = {'provider': 'openai-codex', 'model': 'synthetic-fixed'}
            original = backend.read()
            self.assertTrue(self.call(manager, 'config approve-map base')['ok'])
            self.assertEqual(ctx.settings['roles'], approved_base())
            self.assertTrue(self.call(manager, 'config approve-map auxiliary')['ok'])
            self.assertEqual(ctx.settings['roles'], approved_base())
            self.assertTrue(self.call(manager, 'mode auto')['ok'])
            self.assertTrue(self.call(manager, 'apply')['ok'])
            self.assertEqual(backend.read()['auxiliary'], pins)
            self.assertNotIn('reasoning_effort', backend.read()['auxiliary']['voice_chat'])
            self.assertEqual(backend.read()['image_gen'], original['image_gen'])
            self.assertTrue(self.call(manager, 'mode off')['ok'])
            self.assertEqual(backend.read(), original)
            self.assertEqual(ctx.settings['auxiliary_map'], approved_auxiliary())
