from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import mail
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils import timezone

from .checks import production_email_configuration
from .models import EmailVerification
from .security import cache_rate_limited, normalize_email
from .verification import localized_email, localized_page_text


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_VERIFICATION_EXPIRY_SECONDS=600,
    EMAIL_VERIFICATION_MAX_ATTEMPTS=3,
    EMAIL_VERIFICATION_RESEND_COOLDOWN=60,
    EMAIL_VERIFICATION_MAX_SENDS_PER_HOUR=3,
)
class EmailVerificationFlowTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        translation.activate('en')

    def tearDown(self):
        translation.deactivate()
        super().tearDown()

    signup_data = {
        "username": "verify-user",
        "email": "verify@example.com",
        "first_name": "Verify",
        "last_name": "User",
        "password1": "A-secure-password-2026!",
        "password2": "A-secure-password-2026!",
    }

    def signup(self):
        return self.client.post(reverse("signup"), self.signup_data)

    def test_signup_sends_six_digit_code_and_stores_only_hash(self):
        response = self.signup()
        user = get_user_model().objects.get(username="verify-user")
        verification = EmailVerification.objects.get(user=user)
        body = mail.outbox[0].body
        code = next(part for part in body.split() if part.isdigit() and len(part) == 6)

        self.assertRedirects(response, reverse("verify_email"))
        self.assertFalse(user.is_active)
        self.assertNotIn(code, verification.code_digest)
        self.assertTrue(verification.check_code(code))

    def test_unverified_account_cannot_authenticate(self):
        self.signup()
        self.client.post(reverse("login"), {"username": "verify-user", "password": "A-secure-password-2026!"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_correct_code_activates_and_logs_user_in(self):
        self.signup()
        code = next(part for part in mail.outbox[0].body.split() if part.isdigit() and len(part) == 6)
        response = self.client.post(reverse("verify_email"), {"code": code})
        user = get_user_model().objects.get(username="verify-user")

        self.assertTrue(user.is_active)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(response, reverse("cabinet"))

    def test_expired_or_attempt_exhausted_code_is_rejected(self):
        self.signup()
        verification = EmailVerification.objects.get(user__username="verify-user")
        verification.expires_at = timezone.now() - timedelta(seconds=1)
        verification.save(update_fields=["expires_at"])
        response = self.client.post(reverse("verify_email"), {"code": "000000"})
        self.assertContains(response, "expired", status_code=200)

        verification.expires_at = timezone.now() + timedelta(minutes=10)
        verification.failed_attempts = 2
        verification.save(update_fields=["expires_at", "failed_attempts"])
        self.client.post(reverse("verify_email"), {"code": "000000"})
        verification.refresh_from_db()
        self.assertEqual(verification.failed_attempts, 3)
        self.assertTrue(verification.is_locked)

    def test_resend_enforces_cooldown_and_rotates_code(self):
        self.signup()
        first_digest = EmailVerification.objects.get(user__username="verify-user").code_digest
        response = self.client.post(reverse("resend_verification"))
        self.assertContains(response, localized_page_text('en')['sent'], status_code=200)
        self.assertEqual(len(mail.outbox), 1)

        verification = EmailVerification.objects.get(user__username="verify-user")
        verification.resend_available_at = timezone.now() - timedelta(seconds=1)
        verification.save(update_fields=["resend_available_at"])
        self.client.post(reverse("resend_verification"))
        verification.refresh_from_db()
        self.assertEqual(len(mail.outbox), 2)
        self.assertNotEqual(verification.code_digest, first_digest)

    @patch("store.verification.send_mail", side_effect=RuntimeError("SMTP down"))
    def test_delivery_failure_rolls_back_account_creation(self, _send):
        response = self.signup()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="verify-user").exists())

    def test_page_and_email_copy_are_localized_for_all_routes(self):
        self.signup()
        for language in ('ka', 'en', 'ru'):
            with self.subTest(language=language), translation.override(language):
                response = self.client.get(reverse('verify_email'))
                self.assertContains(response, localized_page_text(language)['title'])
                subject, body = localized_email(language)
                self.assertTrue(subject)
                self.assertIn('{code}', body)

    def test_session_loss_recovery_is_normalized_and_non_enumerating(self):
        self.signup()
        verification = EmailVerification.objects.get(user__username='verify-user')
        verification.resend_available_at = timezone.now() - timedelta(seconds=1)
        verification.save(update_fields=['resend_available_at'])
        self.client.session.flush()

        self.assertEqual(self.client.get(reverse('verify_email')).status_code, 200)
        response = self.client.post(reverse('resend_verification'), {'email': ' VERIFY@EXAMPLE.COM '})
        self.assertContains(response, localized_page_text('en')['sent'])
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(self.client.session['pending_verification_user_id'], verification.user_id)

        unknown = self.client.post(reverse('resend_verification'), {'email': 'missing@example.com'})
        self.assertContains(unknown, localized_page_text('en')['sent'])

    def test_recovery_response_shape_does_not_disclose_account_existence(self):
        self.signup()
        verification = EmailVerification.objects.get(user__username='verify-user')
        verification.resend_available_at = timezone.now() - timedelta(seconds=1)
        verification.save(update_fields=['resend_available_at'])
        self.client.session.flush()

        known = self.client.post(reverse('resend_verification'), {'email': 'verify@example.com'})
        self.client.session.flush()
        unknown = self.client.post(reverse('resend_verification'), {'email': 'missing@example.com'})

        for response in (known, unknown):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, localized_page_text('en')['sent'])
            self.assertTrue(response.context['can_verify'])
            self.assertContains(response, 'id_code')

        unknown_code = self.client.post(reverse('verify_email'), {'code': '123456'})
        self.assertEqual(unknown_code.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(get_user_model().objects.get(username='verify-user').is_active)

    def test_verified_account_cannot_be_reactivated_after_admin_suspension(self):
        self.signup()
        code = next(part for part in mail.outbox[0].body.split() if part.isdigit() and len(part) == 6)
        self.client.post(reverse('verify_email'), {'code': code})
        user = get_user_model().objects.get(username='verify-user')
        verification = EmailVerification.objects.get(user=user)
        self.assertIsNone(verification.pending_verification_at)
        user.is_active = False
        user.save(update_fields=['is_active'])
        self.client.logout()

        response = self.client.post(reverse('resend_verification'), {'email': 'verify@example.com'})
        self.assertContains(response, localized_page_text('en')['sent'])
        self.assertEqual(len(mail.outbox), 1)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    @override_settings(SIGNUP_RATE_LIMIT_PER_IP=1, SIGNUP_RATE_LIMIT_PER_EMAIL=3)
    def test_signup_is_cache_throttled_by_ip_before_delivery(self):
        self.signup()
        second = dict(self.signup_data)
        second.update({'username': 'second-user', 'email': 'second@example.com'})
        response = self.client.post(reverse('signup'), second)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='second-user').exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_cache_throttle_uses_one_key_for_normalized_email_variants(self):
        first = normalize_email(' Verify@Example.COM ')
        second = normalize_email('verify@example.com')

        self.assertFalse(cache_rate_limited('email-test', first, 1, 60))
        self.assertTrue(cache_rate_limited('email-test', second, 1, 60))

    @override_settings(
        DEBUG=False,
        TESTING=False,
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST='smtp.example.com',
        EMAIL_HOST_USER='smtp-user',
        EMAIL_HOST_PASSWORD='smtp-password',
        DEFAULT_FROM_EMAIL='noreply@example.com',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    )
    def test_production_system_check_requires_shared_cache(self):
        errors = production_email_configuration(None)
        self.assertEqual([error.id for error in errors], ['store.E006'])

        with self.settings(CACHES={
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': 'redis://cache.example:6379/1',
            },
        }):
            self.assertEqual(production_email_configuration(None), [])

    def test_database_rejects_case_insensitive_duplicate_email(self):
        self.signup()
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user(
                username='duplicate-user',
                email='VERIFY@EXAMPLE.COM',
                password='A-secure-password-2026!',
            )

    @override_settings(DEBUG=False, TESTING=False)
    def test_production_email_system_check_rejects_test_backends(self):
        with self.assertRaises(SystemCheckError):
            call_command('check', verbosity=0)

    def test_external_next_url_is_not_used_after_verification(self):
        response = self.client.post(reverse("signup") + "?next=https://evil.example/", self.signup_data)
        self.assertRedirects(response, reverse("verify_email"))
        code = next(part for part in mail.outbox[0].body.split() if part.isdigit() and len(part) == 6)
        verified = self.client.post(reverse("verify_email"), {"code": code})
        self.assertRedirects(verified, reverse("cabinet"))
