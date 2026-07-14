from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Coupon, Order
from .services import valid_coupon


class AuthenticationHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="hardened-user", email="hardened@example.com", password="A-test-password-2026!",
        )

    @override_settings(LOGIN_RATE_LIMIT_PER_IP=1, LOGIN_RATE_LIMIT_PER_ACCOUNT=5, LOGIN_RATE_LIMIT_WINDOW=900)
    def test_login_throttle_survives_a_new_browser_session(self):
        self.client.post(reverse("login"), {"username": self.user.username, "password": "wrong-password"})
        fresh_client = Client()
        response = fresh_client.post(reverse("login"), {"username": self.user.username, "password": "wrong-password"})
        self.assertContains(response, "Too many sign-in attempts")

    @override_settings(ADMIN_LOGIN_RATE_LIMIT_PER_IP=1, ADMIN_LOGIN_RATE_LIMIT_PER_ACCOUNT=5, ADMIN_LOGIN_RATE_LIMIT_WINDOW=900)
    def test_admin_login_is_throttled_by_shared_cache(self):
        self.client.post("/admin/login/", {"username": self.user.username, "password": "wrong-password"})
        response = Client().post("/admin/login/", {"username": self.user.username, "password": "wrong-password"})
        self.assertEqual(response.status_code, 429)

    def test_password_reset_routes_are_available(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset your password")

    def test_account_forms_render_accessible_password_visibility_toggles(self):
        for route_name in ("login", "signup"):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertContains(response, "data-password-toggle")
                self.assertContains(response, "aria-pressed=\"false\"")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_sends_a_signed_link_without_account_enumeration(self):
        response = self.client.post(reverse("password_reset"), {"email": self.user.email})
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/reset/", mail.outbox[0].body)


class CommerceAndUploadHardeningTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="coupon-user", email="coupon@example.com", password="A-test-password-2026!",
        )

    def test_coupon_can_be_limited_per_authenticated_customer(self):
        coupon = Coupon.objects.create(code="ONCE", discount_percent=10, max_uses_per_user=1)
        Order.objects.create(
            user=self.user,
            coupon=coupon,
            reference="NX-COUPON-USED",
            full_name="Coupon User",
            email=self.user.email,
            address="1 Test Street",
            total=Decimal("100.00"),
        )
        self.assertIsNone(valid_coupon(coupon.pk, Decimal("100.00"), user=self.user))

    def test_video_validation_rejects_a_disguised_executable(self):
        from .models import validate_video_upload

        upload = SimpleUploadedFile("not-a-video.mp4", b"MZ executable payload", content_type="video/mp4")
        with self.assertRaisesMessage(Exception, "valid video"):
            validate_video_upload(upload)
