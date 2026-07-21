from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from .gemini import gemini_guide_reply


class GeminiGuideTests(SimpleTestCase):
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

    @override_settings(GEMINI_ENABLED=True, GEMINI_API_KEY='')
    def test_guide_does_not_call_network_without_key(self):
        self.assertIsNone(gemini_guide_reply(message='Hello', language='en', products=[]))

    @override_settings(GEMINI_ENABLED=True, GEMINI_API_KEY='replace-with-google-ai-studio-key')
    def test_guide_ignores_example_placeholder(self):
        self.assertIsNone(gemini_guide_reply(message='Hello', language='en', products=[]))
