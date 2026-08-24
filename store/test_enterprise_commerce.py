import io
import tempfile
from decimal import Decimal

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Cart, CartItem, Category, Order, Product, ProductMedia


class PersistentCartAndSearchTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()
        self.category = Category.objects.create(
            name="Smartphones",
            name_en="Smartphones",
            name_ka="სმარტფონები",
            name_ru="Смартфоны",
            slug="enterprise-smartphones",
        )
        self.product = self._product(
            name="NEXORA Travel Camera Phone",
            name_ka="სამოგზაურო კამერიანი ტელეფონი",
            sku="NX-TRAVEL-001",
        )
        self.user = get_user_model().objects.create_user(
            username="persistent-shopper",
            email="shopper@example.com",
            password="safe-password-123",
        )

    def tearDown(self):
        self.media_override.disable()
        self.temp_media.cleanup()
        super().tearDown()

    def _product(self, *, name, name_ka, sku):
        product = Product.objects.create(
            category=self.category,
            primary_category=self.category,
            name=name,
            name_en=name,
            name_ka=name_ka,
            name_ru=name,
            slug=sku.lower(),
            sku=sku,
            brand="NEXORA",
            description="A premium camera phone for travel photography",
            short_description="Travel photography phone",
            price=Decimal("1200.00"),
            stock=8,
            is_active=True,
            is_published=True,
            status="active",
        )
        stream = io.BytesIO()
        Image.new("RGB", (640, 640), "navy").save(stream, "WEBP")
        ProductMedia.objects.create(
            product=product,
            image_file=SimpleUploadedFile(
                f"{sku}.webp", stream.getvalue(), content_type="image/webp"
            ),
            source_url=f"https://example.com/{sku}",
            source_item_id=sku,
            licence_note="Test fixture",
            image_sha256=(sku.encode().hex() + "0" * 64)[:64],
            perceptual_hash=(sku.encode().hex() + "0" * 16)[:16],
            is_verified=True,
            is_primary=True,
            alt_text_en=name,
        )
        return product

    def test_authenticated_cart_is_persisted_across_sessions(self):
        self.client.force_login(self.user)
        self.client.post(reverse("add", args=[self.product.pk]), {"quantity": 2})

        item = CartItem.objects.get(cart__user=self.user, product=self.product)
        self.assertEqual(item.quantity, 2)
        self.assertNotIn("bag", self.client.session)

        another_device = Client()
        another_device.force_login(self.user)
        response = another_device.get(reverse("bag"))
        self.assertEqual(response.context["total"], Decimal("2400.00"))

    def test_guest_cart_merges_into_database_cart_on_login(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.client.post(reverse("add", args=[self.product.pk]), {"quantity": 2})

        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": "safe-password-123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            CartItem.objects.get(cart=cart, product=self.product).quantity,
            3,
        )
        self.assertNotIn("bag", self.client.session)

    def test_checkout_consumes_database_cart_atomically(self):
        self.client.force_login(self.user)
        self.client.post(reverse("add", args=[self.product.pk]), {"quantity": 2})

        response = self.client.post(
            reverse("checkout"),
            {
                "full_name": "Nika Example",
                "email": "nika@example.com",
                "phone": "+995555123456",
                "address": "1 Rustaveli Avenue",
                "city": "Tbilisi",
                "postal_code": "0108",
                "payment_method": "cash_on_delivery",
                "accept_terms": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Order.objects.filter(user=self.user).exists())
        self.assertFalse(CartItem.objects.filter(cart__user=self.user).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 6)

    def test_search_matches_localized_catalog_content_on_sqlite_fallback(self):
        response = self.client.get(reverse("shop"), {"q": "სამოგზაურო"})
        self.assertIn(self.product, response.context["products"].object_list)

        response = self.client.get(reverse("shop"), {"q": "photography"})
        self.assertIn(self.product, response.context["products"].object_list)
