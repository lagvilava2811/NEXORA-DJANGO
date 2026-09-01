"""Transactional email delivery with SMTP and Resend HTTP transports."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import send_mail


class EmailDeliveryError(RuntimeError):
    """Raised when the configured transactional provider declines a message."""


def _send_with_resend(*, subject, text_body, html_body, recipient):
    api_key = settings.RESEND_API_KEY
    if not api_key:
        raise EmailDeliveryError('RESEND_API_KEY is not configured')

    payload = json.dumps(
        {
            'from': settings.DEFAULT_FROM_EMAIL,
            'to': [recipient],
            'subject': subject,
            'text': text_body,
            'html': html_body,
        }
    ).encode('utf-8')
    request = Request(
        settings.RESEND_API_URL,
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'NEXORA/1.0',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:
            if not 200 <= response.status < 300:
                raise EmailDeliveryError(f'Resend returned HTTP {response.status}')
    except (HTTPError, URLError, OSError) as exc:
        raise EmailDeliveryError('Resend delivery request failed') from exc
    return 1


def send_transactional_email(*, subject, text_body, html_body, recipient):
    """Send one transactional message using the configured, server-only transport."""
    provider = settings.NEXORA_EMAIL_PROVIDER
    if provider == 'resend':
        return _send_with_resend(
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            recipient=recipient,
        )
    if provider != 'smtp':
        raise EmailDeliveryError(f'Unsupported NEXORA_EMAIL_PROVIDER: {provider}')
    return send_mail(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
        fail_silently=False,
        html_message=html_body,
    )
