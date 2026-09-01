import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from .email_delivery import EmailDeliveryError, send_transactional_email


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


@override_settings(
    NEXORA_EMAIL_PROVIDER='resend',
    RESEND_API_KEY='re_test_key',
    RESEND_API_URL='https://api.resend.test/emails',
    DEFAULT_FROM_EMAIL='NEXORA <noreply@example.com>',
)
class ResendDeliveryTests(SimpleTestCase):
    @patch('store.email_delivery.urlopen', return_value=_Response())
    def test_resend_transport_posts_html_and_text_to_https_api(self, mocked_open):
        self.assertEqual(
            send_transactional_email(
                subject='Verify',
                text_body='Plain',
                html_body='<b>HTML</b>',
                recipient='buyer@example.com',
            ),
            1,
        )
        request = mocked_open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.resend.test/emails')
        self.assertEqual(request.get_header('Authorization'), 'Bearer re_test_key')
        self.assertEqual(
            json.loads(request.data.decode('utf-8')),
            {
                'from': 'NEXORA <noreply@example.com>',
                'to': ['buyer@example.com'],
                'subject': 'Verify',
                'text': 'Plain',
                'html': '<b>HTML</b>',
            },
        )

    @override_settings(RESEND_API_KEY='')
    def test_resend_requires_server_side_api_key(self):
        with self.assertRaises(EmailDeliveryError):
            send_transactional_email(
                subject='Verify', text_body='Plain', html_body='<b>HTML</b>', recipient='buyer@example.com'
            )
