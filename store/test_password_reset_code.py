import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils import timezone

from .models import PasswordResetCode


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_RESET_CODE_EXPIRY_SECONDS=600,
    PASSWORD_RESET_CODE_MAX_ATTEMPTS=3,
    PASSWORD_RESET_CODE_RESEND_COOLDOWN=60,
    PASSWORD_RESET_CODE_MAX_SENDS_PER_HOUR=3,
)
class PasswordResetCodeFlowTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password="Old-strong-password-2026!",
        )
        translation.activate("en")

    def tearDown(self):
        translation.deactivate()
        super().tearDown()

    def _request_code(self, email=None):
        return self.client.post(reverse("password_reset"), {"email": email or self.user.email})

    def _extract_code(self):
        match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_password_reset_sends_six_digit_code_and_stores_only_hash(self):
        response = self._request_code()
        self.assertRedirects(response, reverse("password_reset_done"))

        record = PasswordResetCode.objects.get(user=self.user)
        code = self._extract_code()

        self.assertTrue(record.check_code(code))
        self.assertNotIn(code, record.code_digest)
        self.assertNotIn("/reset/", mail.outbox[-1].body)

    def test_password_reset_unknown_email_keeps_same_redirect_and_response_shape(self):
        response = self._request_code("missing@example.com")
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

        follow_up = self.client.get(reverse("password_reset_done"))
        self.assertContains(follow_up, "Enter the six-digit code", status_code=200)
        self.assertContains(follow_up, "id_code", status_code=200)

    def test_reset_code_screen_uses_a_compact_responsive_verification_panel(self):
        self._request_code()

        response = self.client.get(reverse("password_reset_done"))

        self.assertContains(response, 'class="auth-section reset-flow"')
        self.assertContains(response, 'class="reset-card auth-card"')
        self.assertContains(response, 'class="reset-code-input"')
        self.assertContains(response, 'class="reset-resend"')

    def test_correct_code_unlocks_password_change_and_invalidates_code_after_use(self):
        self._request_code()
        code = self._extract_code()

        verify = self.client.post(reverse("password_reset_done"), {"code": code})
        self.assertRedirects(verify, reverse("password_reset_confirm"))

        confirm = self.client.post(
            reverse("password_reset_confirm"),
            {
                "new_password1": "New-strong-password-2026!",
                "new_password2": "New-strong-password-2026!",
            },
        )
        self.assertRedirects(confirm, reverse("password_reset_complete"))
        self.assertTrue(
            self.client.login(username=self.user.username, password="New-strong-password-2026!")
        )

        record = PasswordResetCode.objects.get(user=self.user)
        self.assertFalse(record.pending_reset_at)
        self.assertFalse(record.code_digest)

        replay = self.client.post(reverse("password_reset_done"), {"code": code})
        self.assertContains(replay, "invalid", status_code=200)
        self.assertNotIn("password_reset_verified_record_id", self.client.session)

    def test_expired_and_locked_codes_are_rejected(self):
        self._request_code()
        record = PasswordResetCode.objects.get(user=self.user)
        record.expires_at = timezone.now() - timedelta(seconds=1)
        record.save(update_fields=["expires_at"])

        expired = self.client.post(reverse("password_reset_done"), {"code": "000000"})
        self.assertContains(expired, "expired", status_code=200)

        record.refresh_from_db()
        record.expires_at = timezone.now() + timedelta(minutes=10)
        record.failed_attempts = 2
        record.save(update_fields=["expires_at", "failed_attempts"])

        self.client.post(reverse("password_reset_done"), {"code": "000000"})
        record.refresh_from_db()
        self.assertEqual(record.failed_attempts, 3)
        self.assertTrue(record.is_locked)

    def test_resend_rotates_code_after_cooldown(self):
        self._request_code()
        record = PasswordResetCode.objects.get(user=self.user)
        first_digest = record.code_digest

        too_soon = self.client.post(reverse("password_reset_resend"))
        self.assertContains(too_soon, "If an account exists", status_code=200)
        self.assertEqual(len(mail.outbox), 1)

        record.resend_available_at = timezone.now() - timedelta(seconds=1)
        record.save(update_fields=["resend_available_at"])

        resent = self.client.post(reverse("password_reset_resend"))
        self.assertContains(resent, "If an account exists", status_code=200)
        self.assertEqual(len(mail.outbox), 2)

        record.refresh_from_db()
        self.assertNotEqual(record.code_digest, first_digest)
