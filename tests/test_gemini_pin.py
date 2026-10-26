"""Kalıcı (pinned) Gemini yapılandırmasının kod, şablon ve fabrika ile uyumu."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from society.agenda_api import (GEMINI_ENDPOINT, GEMINI_MIN_INTERVAL, GEMINI_MODEL,
                                GROQ_MIN_INTERVAL, GeminiAdvisor, OpenAICompatibleAdvisor,
                                advisor_from_environment)
from society.termux import settings

ROOT = Path(__file__).resolve().parents[1]


class PinnedGeminiTests(unittest.TestCase):
    def pinned_env(self, **extra):
        return {'PEOPLE1000_API_KEY': 'dummy', 'PEOPLE1000_API_ENDPOINT': GEMINI_ENDPOINT, **extra}

    def test_model_is_stable_id_not_rolling_alias(self):
        self.assertEqual(GEMINI_MODEL, 'gemini-3.5-flash-lite')
        self.assertFalse(GEMINI_MODEL.endswith('-latest'))
        self.assertEqual(GEMINI_ENDPOINT,
            'https://generativelanguage.googleapis.com/v1beta/models/'+GEMINI_MODEL+':generateContent')

    def test_env_template_matches_constants_and_has_no_live_key(self):
        text = (ROOT / '.env.example').read_text(encoding='utf-8')
        self.assertIn("export PEOPLE1000_API_ENDPOINT='"+GEMINI_ENDPOINT+"'", text)
        self.assertIn("export PEOPLE1000_API_MODEL='"+GEMINI_MODEL+"'", text)
        self.assertIn('export PEOPLE1000_API_MIN_INTERVAL='+str(int(GEMINI_MIN_INTERVAL)), text)
        key_lines = [line for line in text.splitlines() if 'PEOPLE1000_API_KEY' in line]
        self.assertTrue(key_lines, 'şablonda anahtar satırı olmalı')
        for line in key_lines:
            self.assertTrue(line.lstrip().startswith('#'), 'gerçek anahtar şablonda yorum dışı olamaz')

    def test_factory_infers_pinned_model_and_paces_requests(self):
        with patch.dict(os.environ, self.pinned_env(), clear=True):
            advisor = advisor_from_environment()
        self.assertIsInstance(advisor, GeminiAdvisor)
        self.assertEqual(advisor.model, GEMINI_MODEL)
        self.assertEqual(advisor.endpoint, GEMINI_ENDPOINT)
        self.assertEqual(advisor.min_interval, GEMINI_MIN_INTERVAL)
        self.assertEqual(settings(advisor)['min_interval_seconds'], GEMINI_MIN_INTERVAL)
        with patch.dict(os.environ, self.pinned_env(PEOPLE1000_API_MIN_INTERVAL='2'), clear=True):
            self.assertEqual(advisor_from_environment().min_interval, 2.0)

    def test_key_only_environment_uses_pinned_preset(self):
        # Sabit ayar tek kaynak: adres/model boşsa kod sabitleri uygulanır.
        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'dummy'}, clear=True):
            advisor = advisor_from_environment()
        self.assertIsInstance(advisor, GeminiAdvisor)
        self.assertEqual(advisor.model, GEMINI_MODEL)
        self.assertEqual(advisor.endpoint, GEMINI_ENDPOINT)
        self.assertEqual(advisor.max_output_tokens, 4096)
        with patch.dict(os.environ, {'PEOPLE1000_API_KEY': 'dummy',
                                     'PEOPLE1000_API_MODEL': GEMINI_MODEL}, clear=True):
            with self.assertRaisesRegex(ValueError, 'API adresi eksik'):
                advisor_from_environment()

    def test_compatibility_address_still_rewrites_to_native(self):
        env = {'PEOPLE1000_API_KEY': 'dummy',
               'PEOPLE1000_API_ENDPOINT': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
               'PEOPLE1000_API_MODEL': GEMINI_MODEL}
        with patch.dict(os.environ, env, clear=True):
            advisor = advisor_from_environment()
        self.assertIsInstance(advisor, GeminiAdvisor)
        self.assertEqual(advisor.endpoint, GEMINI_ENDPOINT)
        self.assertEqual(advisor.min_interval, GEMINI_MIN_INTERVAL)

    def test_groq_default_is_unchanged_and_other_providers_unpaced(self):
        groq = {'PEOPLE1000_API_KEY': 'dummy',
                'PEOPLE1000_API_ENDPOINT': 'https://api.groq.com/openai/v1/chat/completions',
                'PEOPLE1000_API_MODEL': 'test-model'}
        with patch.dict(os.environ, groq, clear=True):
            a = advisor_from_environment()
        self.assertIsInstance(a, OpenAICompatibleAdvisor)
        self.assertEqual(a.min_interval, GROQ_MIN_INTERVAL)
        other = {**groq, 'PEOPLE1000_API_ENDPOINT': 'https://example.invalid/v1/chat/completions'}
        with patch.dict(os.environ, other, clear=True):
            self.assertEqual(advisor_from_environment().min_interval, 0.0)


if __name__ == '__main__':
    unittest.main()
