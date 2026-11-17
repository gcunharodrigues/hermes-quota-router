# Characterization controls: README.md HQR-25/HQR-34; readings.normalize and settings.load contracts.
"""Existing exhausted/unknown distinctions and per-field defaults; not additional RED evidence."""
import copy
import json
import unittest

import test_s2_commands as fixtures
from quota_router.mapping import approved_base
from quota_router.render import render
from s2_fakes import claude, codex, reader_for


class QuotaMeaningControls(unittest.TestCase):
    def test_reported_exhaustion_is_not_the_same_as_an_unavailable_reading(self):
        for snapshot, expected_state in ((claude(100), 'ok'), (None, 'unknown')):
            with self.subTest(expected_state=expected_state):
                manager, _, _ = fixtures.manager(fixtures.Context({'mode': 'observe'}),
                                                reader_for(openai_codex=codex(10), anthropic=snapshot), jobs=[])
                self.addCleanup(manager.close)
                payload = json.loads(manager.command('status --json'))
                reading = payload['quota']['providers']['anthropic']
                self.assertEqual(reading['state'], expected_state)
                line = next(line for line in render('status', payload).splitlines() if '**Claude**' in line)
                if snapshot is None:
                    self.assertEqual(reading['windows'], [])
                    self.assertIn('leitura indisponível', line)
                    self.assertNotIn('100%', line)
                    self.assertNotIn('esgotada', line)
                else:
                    self.assertEqual(reading['windows'][0]['used_pct'], 100)
                    self.assertIn('semana 100% usada (esgotada)', line)

    def test_invalid_field_defaults_are_named_without_replacing_the_valid_map(self):
        roles = copy.deepcopy(approved_base())
        roles['general']['anthropic']['effort'] = 'low'
        ctx = fixtures.Context({'mode': 'observe', 'roles': roles, 'limits.week_block_pct': 150})
        manager, _, _ = fixtures.manager(ctx, reader_for(openai_codex=codex(10), anthropic=claude(10)), jobs=[])
        self.addCleanup(manager.close)
        payload = json.loads(manager.command('explain --json'))
        self.assertEqual(set(payload['settings_invalid']), {'limits.week_block_pct'})
        self.assertEqual(payload['settings']['limits.week_block_pct'], 100)
        self.assertEqual(payload['settings']['roles'], roles)
        self.assertEqual(payload['map']['source'], 'settings.roles')
        text = render('explain', payload)
        self.assertIn('`limits.week_block_pct` tem um valor inválido; o plugin usa o padrão', text)
        self.assertIn('Claude claude-opus-5-5 low', text)
        self.assertEqual(ctx.writes, [])


if __name__ == '__main__':
    unittest.main()
