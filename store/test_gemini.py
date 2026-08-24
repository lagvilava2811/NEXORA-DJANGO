from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from .gemini import gemini_guide_reply, meta_guide_reply


class GeminiGuideTests(SimpleTestCase):
    def tearDown(self):
        cache.clear()

    @override_settings(GEMINI_ENABLED=True, GEMINI_API_KEY='test-gemini-key', GEMINI_MODEL='gemini-2.5-flash-lite')
    @patch('store.gemini.requests.post')
    def test_guide_uses_header_key_and_returns_text(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'candidates': [{'content': {'parts': [{'text': 'A concise answer.'}]}}]}
        post.return_value = response

        reply = gemini_guide_reply(message='Recommend a phone', language='en', products=[])

        self.assertEqual(reply, 'A concise answer.')
        self.assertEqual(post.call_args.kwargs['headers']['x-goog-api-key'], 'test-gemini-key')
        self.assertNotIn('key=', post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs['timeout'], (2, 6))

    @override_settings(
        GEMINI_ENABLED=True,
        GEMINI_API_KEY='test-gemini-key',
        GEMINI_MODEL='gemini-test-failure',
        GEMINI_MAX_ATTEMPTS=1,
        GEMINI_FAILURE_COOLDOWN_SECONDS=20,
    )
    @patch('store.gemini.logger.warning')
    @patch('store.gemini.requests.post', side_effect=requests.ConnectionError('network unavailable'))
    def test_failure_opens_short_circuit_breaker(self, post, warning):
        self.assertIsNone(gemini_guide_reply(message='Recommend a phone', language='en', products=[]))
        self.assertIsNone(gemini_guide_reply(message='Recommend a phone', language='en', products=[]))
        self.assertEqual(post.call_count, 1)
        warning.assert_called_once()

    @override_settings(GEMINI_ENABLED=True, GEMINI_API_KEY='')
    def test_guide_does_not_call_network_without_key(self):
        self.assertIsNone(gemini_guide_reply(message='Hello', language='en', products=[]))

    @override_settings(GEMINI_ENABLED=True, GEMINI_API_KEY='replace-with-google-ai-studio-key')
    def test_guide_ignores_example_placeholder(self):
        self.assertIsNone(gemini_guide_reply(message='Hello', language='en', products=[]))

    @override_settings(
        META_MODEL_ENABLED=True,
        META_MODEL_API_KEY='test-meta-key',
        META_MODEL='muse-spark-1.1',
        META_MODEL_MAX_ATTEMPTS=1,
    )
    @patch('store.gemini.requests.post')
    def test_meta_model_api_uses_openai_compatible_contract(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'choices': [{'message': {'content': 'A concise catalog-grounded answer.'}}]
        }
        post.return_value = response

        reply = meta_guide_reply(message='Recommend a phone', language='en', products=[])

        self.assertEqual(reply, 'A concise catalog-grounded answer.')
        self.assertEqual(post.call_args.args[0], 'https://api.meta.ai/v1/chat/completions')
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer test-meta-key')
        self.assertEqual(post.call_args.kwargs['json']['model'], 'muse-spark-1.1')
