import secrets
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import EmailVerification
from .email_delivery import send_transactional_email


logger = logging.getLogger(__name__)


class VerificationDeliveryError(Exception):
    pass


class VerificationCooldownError(Exception):
    pass


class VerificationRateLimitError(Exception):
    pass


class VerificationStateError(Exception):
    pass


EMAIL_SUBJECT_EN = 'Confirm your NEXORA email'
EMAIL_BODY_EN = 'Confirm your email with this one-time link:\n\n{link}\n\nThis link expires in {minutes} minutes. If you did not create a NEXORA account, you can safely ignore this email.'
EMAIL_SUBJECT_KA = 'NEXORA — \u10d3\u10d0\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d7 \u10d4\u10da\u10e4\u10dd\u10e1\u10e2\u10d0'
EMAIL_BODY_KA = '\u10d3\u10d0\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d7 \u10d7\u10e5\u10d5\u10d4\u10dc\u10d8 \u10d4\u10da\u10e4\u10dd\u10e1\u10e2\u10d0 \u10d0\u10db \u10d4\u10e0\u10d7\u10ef\u10d4\u10e0\u10d0\u10d3\u10d8 \u10d1\u10db\u10e3\u10da\u10d8\u10d7:\n\n{link}\n\n\u10d1\u10db\u10e3\u10da\u10d8 \u10db\u10dd\u10e5\u10db\u10d4\u10d3\u10d4\u10d1\u10e1 {minutes} \u10ec\u10e3\u10d7\u10d8.'
EMAIL_SUBJECT_RU = '\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 email NEXORA'
EMAIL_BODY_RU = '\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u0432\u0430\u0448\u0443 \u043f\u043e\u0447\u0442\u0443 \u043f\u043e \u044d\u0442\u043e\u0439 \u043e\u0434\u043d\u043e\u0440\u0430\u0437\u043e\u0432\u043e\u0439 \u0441\u0441\u044b\u043b\u043a\u0435:\n\n{link}\n\n\u0421\u0441\u044b\u043b\u043a\u0430 \u0434\u0435\u0439\u0441\u0442\u0432\u0443\u0435\u0442 {minutes} \u043c\u0438\u043d\u0443\u0442.'


def localized_email(language):
    language = (language or 'en').split('-')[0]
    if language == 'ka':
        return EMAIL_SUBJECT_KA, EMAIL_BODY_KA
    if language == 'ru':
        return EMAIL_SUBJECT_RU, EMAIL_BODY_RU
    return EMAIL_SUBJECT_EN, EMAIL_BODY_EN


PAGE_TEXT = {
    'en': {
        'title': 'Verify your email',
        'intro': 'Open the one-time confirmation link we sent to your email address.',
        'link_sent': 'Your confirmation email is on its way.',
        'email_button': 'Verify email',
        'resend': 'Resend confirmation email',
        'expired': 'This confirmation link has expired. Request a new one.',
        'sent': 'If the account is awaiting verification, a new confirmation link has been sent.',
        'unavailable': 'Verification email is temporarily unavailable. Please try again.',
        'state': 'Unable to start verification for this account. Please sign in or use a different email address.',
    },
}
PAGE_TEXT['ka'] = PAGE_TEXT['en'].copy()
PAGE_TEXT['ka'].update({
    'title': '\u10d3\u10d0\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d7 \u10d4\u10da\u10e4\u10dd\u10e1\u10e2\u10d0',
    'intro': '\u10e8\u10d4\u10d8\u10e7\u10d5\u10d0\u10dc\u10d4\u10d7 \u10d4\u10da\u10e4\u10dd\u10e1\u10e2\u10d0\u10d6\u10d4 \u10d2\u10d0\u10db\u10dd\u10d2\u10d6\u10d0\u10d5\u10dc\u10d8\u10da\u10d8 \u10d4\u10e5\u10d5\u10e1\u10dc\u10d8\u10e8\u10dc\u10d0 \u10d9\u10dd\u10d3\u10d8.',
    'submit': '\u10d0\u10dc\u10d2\u10d0\u10e0\u10d8\u10e8\u10d8\u10e1 \u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d0',
    'resend': '\u10d0\u10ee\u10d0\u10da\u10d8 \u10d9\u10dd\u10d3\u10d8\u10e1 \u10d2\u10d0\u10db\u10dd\u10d2\u10d6\u10d0\u10d5\u10dc\u10d0',
    'invalid': '\u10d9\u10dd\u10d3\u10d8 \u10d0\u10e0\u10d0\u10e1\u10ec\u10dd\u10e0\u10d8\u10d0.',
})
PAGE_TEXT['ru'] = PAGE_TEXT['en'].copy()
PAGE_TEXT['ru'].update({
    'title': '\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u044d\u043b\u0435\u043a\u0442\u0440\u043e\u043d\u043d\u0443\u044e \u043f\u043e\u0447\u0442\u0443',
    'intro': '\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u0448\u0435\u0441\u0442\u0438\u0437\u043d\u0430\u0447\u043d\u044b\u0439 \u043a\u043e\u0434, \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043d\u044b\u0439 \u043d\u0430 \u0432\u0430\u0448\u0443 \u043f\u043e\u0447\u0442\u0443.',
    'submit': '\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c \u0430\u043a\u043a\u0430\u0443\u043d\u0442',
    'resend': '\u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043d\u043e\u0432\u044b\u0439 \u043a\u043e\u0434',
    'invalid': '\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u043a\u043e\u0434.',
})
PAGE_TEXT['ru'].update({
    'expired': '\u0421\u0440\u043e\u043a \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f \u043a\u043e\u0434\u0430 \u0438\u0441\u0442\u0451\u043a. \u0417\u0430\u043f\u0440\u043e\u0441\u0438\u0442\u0435 \u043d\u043e\u0432\u044b\u0439 \u043a\u043e\u0434.',
    'locked': '\u0421\u043b\u0438\u0448\u043a\u043e\u043c \u043c\u043d\u043e\u0433\u043e \u043f\u043e\u043f\u044b\u0442\u043e\u043a. \u0417\u0430\u043f\u0440\u043e\u0441\u0438\u0442\u0435 \u043d\u043e\u0432\u044b\u0439 \u043a\u043e\u0434.',
    'wait': '\u041f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435 \u043f\u0435\u0440\u0435\u0434 \u0437\u0430\u043f\u0440\u043e\u0441\u043e\u043c \u043d\u043e\u0432\u043e\u0433\u043e \u043a\u043e\u0434\u0430.',
    'sent': '\u0415\u0441\u043b\u0438 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u043e\u0436\u0438\u0434\u0430\u0435\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f, \u043d\u043e\u0432\u044b\u0439 \u043a\u043e\u0434 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d.',
    'unavailable': '\u041f\u0438\u0441\u044c\u043c\u043e \u0441 \u043a\u043e\u0434\u043e\u043c \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u043e. \u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435 \u043f\u043e\u043f\u044b\u0442\u043a\u0443.',
    'state': '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043d\u0430\u0447\u0430\u0442\u044c \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435 \u0434\u043b\u044f \u044d\u0442\u043e\u0439 \u0443\u0447\u0451\u0442\u043d\u043e\u0439 \u0437\u0430\u043f\u0438\u0441\u0438.',
})


def localized_page_text(language):
    language = (language or 'en').split('-')[0]
    return PAGE_TEXT.get(language, PAGE_TEXT['en'])
PAGE_TEXT['ka'].update({
    'expired': '\u10d9\u10dd\u10d3\u10d8\u10e1 \u10db\u10dd\u10e5\u10db\u10d4\u10d3\u10d4\u10d1\u10d8\u10e1 \u10d5\u10d0\u10d3\u10d0 \u10d0\u10db\u10dd\u10d8\u10ec\u10e3\u10e0\u10d0. \u10db\u10dd\u10d8\u10d7\u10ee\u10dd\u10d5\u10d4\u10d7 \u10d0\u10ee\u10d0\u10da\u10d8 \u10d9\u10dd\u10d3\u10d8.',
    'locked': '\u10db\u10ea\u10d3\u10d4\u10da\u10dd\u10d1\u10d4\u10d1\u10d8\u10e1 \u10da\u10d8\u10db\u10d8\u10e2\u10d8 \u10d0\u10db\u10dd\u10d8\u10ec\u10e3\u10e0\u10d0. \u10db\u10dd\u10d8\u10d7\u10ee\u10dd\u10d5\u10d4\u10d7 \u10d0\u10ee\u10d0\u10da\u10d8 \u10d9\u10dd\u10d3\u10d8.',
    'wait': '\u10d0\u10ee\u10d0\u10da\u10d8 \u10d9\u10dd\u10d3\u10d8\u10e1 \u10db\u10dd\u10d7\u10ee\u10dd\u10d5\u10dc\u10d0\u10db\u10d3\u10d4 \u10ea\u10dd\u10e2\u10d0\u10ee\u10d0\u10dc\u10e1 \u10d3\u10d0\u10d4\u10da\u10dd\u10d3\u10d4\u10d7.',
    'sent': '\u10d7\u10e3 \u10d0\u10dc\u10d2\u10d0\u10e0\u10d8\u10e8\u10d8 \u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d0\u10e1 \u10d4\u10da\u10dd\u10d3\u10d4\u10d1\u10d0, \u10d0\u10ee\u10d0\u10da\u10d8 \u10d9\u10dd\u10d3\u10d8 \u10d2\u10d0\u10db\u10dd\u10d2\u10d6\u10d0\u10d5\u10dc\u10d8\u10da\u10d8\u10d0.',
    'unavailable': '\u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d8\u10e1 \u10ec\u10d4\u10e0\u10d8\u10da\u10d8 \u10d3\u10e0\u10dd\u10d4\u10d1\u10d8\u10d7 \u10d5\u10d4\u10e0 \u10d8\u10d2\u10d6\u10d0\u10d5\u10dc\u10d4\u10d1\u10d0. \u10e1\u10ea\u10d0\u10d3\u10d4\u10d7 \u10ee\u10d4\u10da\u10d0\u10ee\u10da\u10d0.',
    'state': '\u10d0\u10db \u10d0\u10dc\u10d2\u10d0\u10e0\u10d8\u10e8\u10d8\u10e1\u10d7\u10d5\u10d8\u10e1 \u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d8\u10e1 \u10d3\u10d0\u10ec\u10e7\u10d4\u10d1\u10d0 \u10d5\u10d4\u10e0 \u10db\u10dd\u10ee\u10d4\u10e0\u10ee\u10d3\u10d0. \u10e8\u10d4\u10d3\u10d8\u10d7 \u10d0\u10dc \u10d2\u10d0\u10db\u10dd\u10d8\u10e7\u10d4\u10dc\u10d4\u10d7 \u10e1\u10ee\u10d5\u10d0 \u10d4\u10da\u10e4\u10dd\u10e1\u10e2\u10d0.',
})

# Signup uses a one-time confirmation link; six-digit codes belong only to password reset.
PAGE_TEXT['ka'].update({
    'intro': '\u10d2\u10d0\u10ee\u10e1\u10d4\u10dc\u10d8\u10d7 \u10d4\u10da\u10e4\u10dd\u10e1\u10e2\u10d0\u10d6\u10d4 \u10d2\u10d0\u10db\u10dd\u10d2\u10d6\u10d0\u10d5\u10dc\u10d8\u10da\u10d8 \u10d4\u10e0\u10d7\u10ef\u10d4\u10e0\u10d0\u10d3\u10d8 \u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d8\u10e1 \u10d1\u10db\u10e3\u10da\u10d8.',
    'link_sent': '\u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d8\u10e1 \u10ec\u10d4\u10e0\u10d8\u10da\u10d8 \u10d2\u10d0\u10db\u10dd\u10d2\u10d6\u10d0\u10d5\u10dc\u10d8\u10da\u10d8\u10d0.',
    'email_button': '\u10d4\u10da\u10e4\u10dd\u10e1\u10e2\u10d8\u10e1 \u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d0',
    'resend': '\u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d8\u10e1 \u10ec\u10d4\u10e0\u10d8\u10da\u10d8\u10e1 \u10ee\u10d4\u10da\u10d0\u10ee\u10da\u10d0 \u10d2\u10d0\u10db\u10dd\u10d2\u10d6\u10d0\u10d5\u10dc\u10d0',
    'expired': '\u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d8\u10e1 \u10d1\u10db\u10e3\u10da\u10e1 \u10d5\u10d0\u10d3\u10d0 \u10d2\u10d0\u10e3\u10d5\u10d8\u10d3\u10d0. \u10db\u10dd\u10d8\u10d7\u10ee\u10dd\u10d5\u10d4\u10d7 \u10d0\u10ee\u10d0\u10da\u10d8 \u10d1\u10db\u10e3\u10da\u10d8.',
    'sent': '\u10d7\u10e3 \u10d0\u10dc\u10d2\u10d0\u10e0\u10d8\u10e8\u10d8 \u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d0\u10e1 \u10d4\u10da\u10dd\u10d3\u10d4\u10d1\u10d0, \u10d0\u10ee\u10d0\u10da\u10d8 \u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d8\u10e1 \u10d1\u10db\u10e3\u10da\u10d8 \u10d2\u10d0\u10db\u10dd\u10d2\u10d6\u10d0\u10d5\u10dc\u10d8\u10da\u10d8\u10d0.',
})
PAGE_TEXT['ru'].update({
    'intro': '\u041e\u0442\u043a\u0440\u043e\u0439\u0442\u0435 \u043e\u0434\u043d\u043e\u0440\u0430\u0437\u043e\u0432\u0443\u044e \u0441\u0441\u044b\u043b\u043a\u0443 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f, \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043d\u0443\u044e \u043d\u0430 \u0432\u0430\u0448\u0443 \u043f\u043e\u0447\u0442\u0443.',
    'link_sent': '\u041f\u0438\u0441\u044c\u043c\u043e \u0441 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435\u043c \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043e.',
    'email_button': '\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c email',
    'resend': '\u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043f\u0438\u0441\u044c\u043c\u043e \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f \u043f\u043e\u0432\u0442\u043e\u0440\u043d\u043e',
    'expired': '\u0421\u0440\u043e\u043a \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f \u0441\u0441\u044b\u043b\u043a\u0438 \u0438\u0441\u0442\u0451\u043a. \u0417\u0430\u043f\u0440\u043e\u0441\u0438\u0442\u0435 \u043d\u043e\u0432\u0443\u044e.',
    'sent': '\u0415\u0441\u043b\u0438 \u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u043e\u0436\u0438\u0434\u0430\u0435\u0442 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f, \u043d\u043e\u0432\u0430\u044f \u0441\u0441\u044b\u043b\u043a\u0430 \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0430.',
})


def mask_email(value):
    local, separator, domain = (value or '').partition('@')
    if not separator:
        return '***'
    visible = local[:2] if len(local) > 2 else local[:1]
    return f'{visible}***@{domain}'


def issue_verification(user, language='en', enforce_cooldown=False, request=None):
    now = timezone.now()
    expiry_seconds = max(60, int(getattr(settings, 'EMAIL_VERIFICATION_EXPIRY_SECONDS', 600)))
    cooldown_seconds = max(1, int(getattr(settings, 'EMAIL_VERIFICATION_RESEND_COOLDOWN', 60)))
    max_sends = max(1, int(getattr(settings, 'EMAIL_VERIFICATION_MAX_SENDS_PER_HOUR', 5)))

    with transaction.atomic():
        record, created = EmailVerification.objects.select_for_update().get_or_create(
            user=user,
            defaults={
                'code_digest': make_password('unissued'),
                'expires_at': now,
                'resend_available_at': now,
                'send_window_started_at': now,
                'pending_verification_at': now,
            },
        )
        if user.is_active or record.verified_at is not None or record.pending_verification_at is None:
            raise VerificationStateError
        if enforce_cooldown and not created and now < record.resend_available_at:
            raise VerificationCooldownError

        window_expired = now >= record.send_window_started_at + timedelta(hours=1)
        send_count = 0 if window_expired else record.send_count
        window_started = now if window_expired else record.send_window_started_at
        if send_count >= max_sends:
            raise VerificationRateLimitError

        link_token = secrets.token_urlsafe(32)
        link_path = reverse('verify_email_link', kwargs={'user_id': user.pk, 'token': link_token})
        if request is not None:
            verification_link = request.build_absolute_uri(link_path)
        else:
            verification_link = f"{getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')}{link_path}"
        minutes = max(1, expiry_seconds // 60)
        subject, body_template = localized_email(language)
        message = body_template.format(link=verification_link, minutes=minutes)
        body = render_to_string('email/verification_code.txt', {'message': message})
        html_body = render_to_string(
            'email/verification_code.html',
            {
                'message': message,
                'language': language,
                'verification_link': verification_link,
                'email_button': localized_page_text(language)['email_button'],
            },
        )
        try:
            sent = send_transactional_email(
                subject=subject,
                text_body=body,
                html_body=html_body,
                recipient=user.email,
            )
        except Exception as exc:
            logger.exception("Verification email delivery failed for pending account")
            raise VerificationDeliveryError from exc
        if sent != 1:
            raise VerificationDeliveryError

        # Email confirmation is link-only. Password reset codes are handled separately.
        record.code_digest = ''
        record.link_token_digest = make_password(link_token)
        record.expires_at = now + timedelta(seconds=expiry_seconds)
        record.resend_available_at = now + timedelta(seconds=cooldown_seconds)
        record.failed_attempts = 0
        record.send_count = send_count + 1
        record.send_window_started_at = window_started
        record.verified_at = None
        record.save()
        return record
