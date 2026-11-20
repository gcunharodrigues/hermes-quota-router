# Contract: decisions/aux-plan.md, "Mapa por tarefa", D-AUXP-1 and D-AUXP-7.
"""Auxiliary proposal data is detached from the approved settings and role map."""
import unittest

from quota_router import mapping


class AuxiliaryMapTests(unittest.TestCase):
    def test_exact_eleven_task_pairs_preserve_provider_effort_and_absence(self):
        self.assertTrue(hasattr(mapping, 'approved_auxiliary'), 'Auxiliary map proposal is missing')
        table = mapping.approved_auxiliary()
        expected = {
            'title_generation': ('gpt-6-luna', 'claude-haiku-5-5', 'low'),
            'profile_describer': ('gpt-6-luna', 'claude-haiku-5-5', 'low'),
            'tts_audio_tags': ('gpt-6-luna', 'claude-haiku-5-5', 'low'),
            'compression': ('gpt-6.1-terra', 'claude-sonnet-5-5', 'medium'),
            'background_review': ('gpt-6.1-terra', 'claude-sonnet-5-5', 'medium'),
            'kanban_decomposer': ('gpt-6.1-terra', 'claude-sonnet-5-5', 'medium'),
            'approval': ('gpt-6.1-terra', 'claude-sonnet-5-5', 'low'),
            'goal_judge': ('gpt-6.1-terra', 'claude-sonnet-5-5', 'low'),
            'monitor': ('gpt-6.1-terra', 'claude-sonnet-5-5', 'low'),
            'triage_specifier': ('gpt-6.1-terra', 'claude-sonnet-5-5', 'low'),
            'voice_chat': ('gpt-6.1-terra', 'claude-sonnet-5-5', 'low'),
        }
        self.assertEqual(set(table), set(expected))
        for task, (codex, claude, effort) in expected.items():
            with self.subTest(task=task):
                self.assertEqual(set(table[task]), {'openai-codex', 'anthropic'})
                self.assertEqual(table[task]['openai-codex'], {'model': codex, 'effort': effort})
                target = {'model': claude} if task == 'approval' else {'model': claude, 'effort': effort}
                self.assertEqual(table[task]['anthropic'], target)
        table['approval']['anthropic']['effort'] = 'high'
        table.pop('voice_chat')
        fresh = mapping.approved_auxiliary()
        self.assertNotIn('effort', fresh['approval']['anthropic'])
        self.assertIn('voice_chat', fresh)
        self.assertNotIn('image_gen', fresh)
        self.assertNotIn('approval', mapping.approved_base())
