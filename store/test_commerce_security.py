import io
import tempfile
from datetime import timedelta
from decimal import Decimal

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Category, Coupon, Order, Product, ProductMedia, UserAddress


def image_bytes(color):
    stream = io.BytesIO()
    Image.new("RGB", (640, 640), color).save(stream, "WEBP")
    return stream.getvalue()


class StorefrontSecurityTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()
        self.category = Category.objects.create(
            name="Smartphones",
            name_en="Smartphones",
            name_ka="სმარტფონები",
            name_ru="Смартфоны",
            slug="security-smartphones",
        )
        self.product = self.create_published_product("Secure Phone", "SECURE-001", "navy")
        self.user = get_user_model().objects.create_user(
            username="owner", email="owner@example.com", password="strong-password-123"
        )

    def tearDown(self):
        self.media_override.disable()
        self.temp_media.cleanup()

    def create_published_product(self, name, sku, color):
        product = Product.objects.create(
            category=self.category,
            primary_category=self.category,
            name=name,
            name_en=name,
            slug=f"{sku.lower()}-product",
            sku=sku,
            description="Verified exact model",
            price=Decimal("999.00"),
            stock=3,
            is_active=True,
            is_published=True,
            status="active",
        )
        ProductMedia.objects.create(
            product=product,
            image_file=SimpleUploadedFile(f"{sku}.webp", image_bytes(color), content_type="image/webp"),
            source_url=f"https://commons.wikimedia.org/wiki/File:{sku}.webp",
            licence_note="CC BY-SA 4.0",
            image_sha256=(sku.encode().hex() + "0" * 64)[:64],
            perceptual_hash=(sku.encode().hex() + "0" * 16)[:16],
            is_verified=True,
            is_primary=True,
            alt_text_en=name,
        )
        return product

    def checkout_payload(self):
        return {
            "full_name": "Nika Example",
            "email": "nika@example.com",
            "phone": "+995555123456",
            "address": "1 Rustaveli Avenue",
            "city": "Tbilisi",
            "postal_code": "0108",
            "payment_method": "cash_on_delivery",
            "notes": "",
            "accept_terms": "on",
        }

    def add_to_bag(self, quantity=1):
        response = self.client.post(reverse("add", args=[self.product.pk]), {"quantity": quantity})
        self.assertEqual(response.status_code, 302)

    def test_storefront_and_cart_exclude_unpublished_products(self):
        hidden = Product.objects.create(
            category=self.category,
            name="Hidden Device",
            slug="hidden-device",
            sku="HIDDEN-001",
            description="Draft",
            price=1,
            stock=5,
            is_active=True,
            is_published=False,
        )
        self.assertContains(self.client.get(reverse("home")), self.product.name)
        self.assertNotContains(self.client.get(reverse("shop")), hidden.name)
        self.assertEqual(self.client.get(reverse("product", args=[hidden.slug])).status_code, 404)
        self.assertEqual(self.client.post(reverse("add", args=[hidden.pk]), {"quantity": 1}).status_code, 404)

    def test_mutating_endpoints_reject_get(self):
        self.client.force_login(self.user)
        address = UserAddress.objects.create(
            user=self.user,
            title="Home",
            full_name="Owner",
            phone="555",
            city="Tbilisi",
            address_line="Street",
        )
        endpoints = [
            reverse("add", args=[self.product.pk]),
            reverse("update", args=[self.product.pk]),
            reverse("cart_add_ajax", args=[self.product.pk]),
            reverse("cart_update_ajax", args=[self.product.pk]),
            reverse("toggle_wishlist", args=[self.product.pk]),
            reverse("toggle_compare", args=[self.product.pk]),
            reverse("add_review", args=[self.product.slug]),
            reverse("delete_address", args=[address.pk]),
            reverse("logout"),
            reverse("apply_coupon"),
            reverse("guide"),
        ]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.client.get(endpoint).status_code, 405)

    def test_checkout_locks_inventory_and_creates_price_snapshots(self):
        self.client.force_login(self.user)
        self.add_to_bag(quantity=2)
        response = self.client.post(reverse("checkout"), self.checkout_payload())
        order = Order.objects.get()
        self.assertRedirects(response, reverse("order_success", args=[order.reference]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(order.items.get().unit_price, Decimal("999.00"))
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(order.user, self.user)

    def test_checkout_rejects_overselling_without_partial_order(self):
        session = self.client.session
        session["bag"] = {str(self.product.pk): 9}
        session.save()
        response = self.client.post(reverse("checkout"), self.checkout_payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only 3 units")
        self.assertFalse(Order.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_order_success_is_private_for_users_and_guest_sessions(self):
        self.client.force_login(self.user)
        self.add_to_bag()
        response = self.client.post(reverse("checkout"), self.checkout_payload())
        order = Order.objects.get()
        self.assertEqual(self.client.get(response.url).status_code, 200)
        stranger = get_user_model().objects.create_user(username="stranger", password="pass-123456")
        other_client = Client()
        other_client.force_login(stranger)
        self.assertEqual(other_client.get(reverse("order_success", args=[order.reference])).status_code, 404)

        guest = Client()
        guest.post(reverse("add", args=[self.product.pk]), {"quantity": 1})
        guest_response = guest.post(reverse("checkout"), self.checkout_payload())
        guest_order = Order.objects.exclude(pk=order.pk).get()
        self.assertEqual(guest.get(guest_response.url).status_code, 200)
        self.assertEqual(Client().get(reverse("order_success", args=[guest_order.reference])).status_code, 404)

    def test_coupon_dates_limits_and_minimum_order_are_enforced(self):
        future = Coupon.objects.create(
            code="FUTURE",
            discount_percent=10,
            valid_from=timezone.now() + timedelta(days=1),
        )
        minimum = Coupon.objects.create(code="MINIMUM", discount_percent=10, min_order_amount=2000)
        self.add_to_bag()
        for coupon in (future, minimum):
            response = self.client.post(reverse("apply_coupon"), {"coupon_code": coupon.code})
            self.assertEqual(response.status_code, 302)
            self.assertIsNone(self.client.session.get("coupon_id"))

    def test_guide_requires_csrf_and_never_returns_unpublished_products(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("guide"),
            data='{"message":"Secure Phone"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse("guide"),
            data='{"message":"Secure Phone"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)

    def test_external_login_next_url_is_not_followed(self):
        response = self.client.post(
            reverse("login") + "?next=https://evil.example/steal",
            {"username": "owner", "password": "strong-password-123"},
        )
        self.assertRedirects(response, reverse("cabinet"))

    def test_invalid_cart_quantity_is_safely_bounded(self):
        response = self.client.post(reverse("cart_add_ajax", args=[self.product.pk]), {"quantity": "not-a-number"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["qty"], 1)
        response = self.client.post(reverse("cart_update_ajax", args=[self.product.pk]), {"quantity": 9999})
        self.assertEqual(response.json()["items"][0]["qty"], self.product.stock)

    def test_storefront_csp_uses_a_per_request_nonce_without_unsafe_inline_styles(self):
        response = self.client.get(reverse("home"))
        csp = response.headers["Content-Security-Policy"]
        nonce = response.context["csp_nonce"]
        self.assertIn(f"script-src 'self' 'nonce-{nonce}'", csp)
        self.assertIn("style-src 'self'", csp)
        self.assertNotIn("style-src 'self' 'unsafe-inline'", csp)
        self.assertContains(response, f'nonce="{nonce}"')
