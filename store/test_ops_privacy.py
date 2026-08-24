import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import AccountDeletionRequest, Category, Order, OrderItem, Product


class HealthEndpointTests(TestCase):
    def test_health_endpoint_checks_database_and_cache_without_exposing_details(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "ok",
            "checks": {"database": True, "cache": True},
        })
        self.assertIn("no-store", response["Cache-Control"])


class LegalPageTests(TestCase):
    def test_legal_pages_are_public_and_localized(self):
        for route_name in ("privacy", "terms", "cookies"):
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "support@nexora.example")


class AccountDataRightsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="privacy-user",
            email="privacy@example.com",
            password="A-test-password-2026!",
        )
        self.other = get_user_model().objects.create_user(
            username="other-user",
            email="other@example.com",
            password="A-test-password-2026!",
        )
        self.category = Category.objects.create(name="Privacy test", slug="privacy-test")
        self.product = Product.objects.create(
            name="Export Device",
            slug="export-device",
            sku="EXPORT-001",
            price=Decimal("100.00"),
            stock=5,
            category=self.category,
        )
        self.order = Order.objects.create(
            user=self.user,
            reference="NX-PRIVACY-1",
            full_name="Privacy User",
            email=self.user.email,
            address="1 Private Street",
            total=Decimal("100.00"),
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            unit_price=Decimal("100.00"),
        )
        Order.objects.create(
            user=self.other,
            reference="NX-OTHER-1",
            full_name="Other User",
            email=self.other.email,
            address="2 Other Street",
            total=Decimal("200.00"),
        )
        self.client.force_login(self.user)

    def test_export_contains_only_authenticated_users_data(self):
        response = self.client.get(reverse("account_data_export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "no-store, private")
        payload = json.loads(response.content)
        self.assertEqual(payload["account"]["email"], self.user.email)
        self.assertEqual([item["reference"] for item in payload["orders"]], ["NX-PRIVACY-1"])
        self.assertNotIn("other@example.com", response.content.decode())

    def test_deletion_request_is_idempotent_and_preserves_orders(self):
        route = reverse("request_account_deletion")
        self.client.post(route)
        self.client.post(route)
        self.assertEqual(AccountDeletionRequest.objects.filter(user=self.user).count(), 1)
        self.assertEqual(self.user.deletion_request.status, "pending")
        self.assertTrue(Order.objects.filter(pk=self.order.pk, user=self.user).exists())

    def test_pending_deletion_request_can_be_cancelled(self):
        AccountDeletionRequest.objects.create(user=self.user)
        response = self.client.post(reverse("cancel_account_deletion"))
        self.assertRedirects(response, reverse("cabinet"))
        self.user.deletion_request.refresh_from_db()
        self.assertEqual(self.user.deletion_request.status, "cancelled")

    def test_data_tools_require_authentication(self):
        self.client.logout()
        for route_name, method in (
            ("account_data_export", self.client.get),
            ("request_account_deletion", self.client.post),
            ("cancel_account_deletion", self.client.post),
        ):
            with self.subTest(route_name=route_name):
                response = method(reverse(route_name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response.url)
