import io
import tempfile
from decimal import Decimal

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, Coupon, Order, Product, ProductMedia, ProductVariant, UserAddress


class PublishedProductMixin:
    def setUp(self):
        super().setUp()
        self.temp_media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()
        self.category = Category.objects.create(
            name="Smartphones", name_en="Smartphones", name_ka="სმარტფონები",
            name_ru="Смартфоны", slug=f"phones-{self.__class__.__name__.lower()}",
        )
        self.product = self.make_product("Nova X Pro", "NOVA-X-001")

    def tearDown(self):
        self.media_override.disable()
        self.temp_media.cleanup()
        super().tearDown()

    def make_product(self, name, sku, **overrides):
        values = {
            "category": self.category, "primary_category": self.category, "name": name,
            "name_en": name, "name_ka": name, "name_ru": name,
            "slug": f"{sku.lower()}-slug", "sku": sku, "description": "AMOLED technology",
            "short_description": "Verified smartphone", "price": Decimal("999.00"),
            "stock": 5, "is_active": True,
            "is_published": True, "status": "active", "specs": {"ram": "8 GB", "storage": "128 GB"},
        }
        values.update(overrides)
        product = Product.objects.create(**values)
        stream = io.BytesIO()
        Image.new("RGB", (640, 640), "navy").save(stream, "WEBP")
        ProductMedia.objects.create(
            product=product,
            image_file=SimpleUploadedFile(f"{sku}.webp", stream.getvalue(), content_type="image/webp"),
            source_url=f"https://commons.wikimedia.org/wiki/File:{sku}.webp",
            source_item_id=f"Q{product.pk}", licence_note="CC BY-SA 4.0",
            image_sha256=(sku.encode().hex() + "0" * 64)[:64],
            perceptual_hash=(sku.encode().hex() + "0" * 16)[:16],
            is_verified=True, is_primary=True, alt_text_en=name,
        )
        return product


class StoreJourneyTests(PublishedProductMixin, TestCase):
    def test_home_product_and_local_media_render(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, self.product.name)
        self.assertContains(response, self.product.display_image)
        self.assertEqual(self.client.get(self.product.get_absolute_url()).status_code, 200)

    def test_bag_total_is_server_calculated(self):
        self.client.post(reverse("add", args=[self.product.pk]), {"quantity": 2})
        response = self.client.get(reverse("bag"))
        self.assertEqual(response.context["total"], Decimal("1998.00"))
        self.assertEqual(self.client.session["bag"][str(self.product.pk)], 2)

    def test_ajax_cart_add_and_update(self):
        response = self.client.post(reverse("cart_add_ajax", args=[self.product.pk]), {"quantity": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["qty"], 2)
        response = self.client.post(reverse("cart_update_ajax", args=[self.product.pk]), {"quantity": 3})
        self.assertEqual(response.json()["items"][0]["qty"], 3)

    def test_variant_is_added_with_its_own_price_and_saved_on_order(self):
        premium = ProductVariant.objects.create(
            product=self.product,
            name="Premium",
            sku="NOVA-X-PREMIUM",
            price_delta=Decimal("240.00"),
            stock_quantity=2,
        )

        response = self.client.post(
            reverse("cart_add_ajax", args=[self.product.pk]),
            {"quantity": 1, "variant": premium.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["price"], "1239.00")
        self.assertIn(f"{self.product.pk}:{premium.pk}", self.client.session["bag"])

        response = self.client.post(reverse("checkout"), {
            "full_name": "Nika Example", "email": "nika@example.com", "phone": "+995555123456",
            "address": "1 Rustaveli Avenue", "city": "Tbilisi", "postal_code": "0108",
            "payment_method": "cash_on_delivery", "accept_terms": "on",
        })
        self.assertEqual(response.status_code, 302)
        item = Order.objects.get().items.get()
        self.assertEqual(item.variant, premium)
        self.assertEqual(item.unit_price, Decimal("1239.00"))

    def test_complete_checkout_journey(self):
        self.client.post(reverse("add", args=[self.product.pk]), {"quantity": 1})
        response = self.client.post(reverse("checkout"), {
            "full_name": "Nika Example", "email": "nika@example.com", "phone": "+995555123456",
            "address": "1 Rustaveli Avenue", "city": "Tbilisi", "postal_code": "0108",
            "payment_method": "cash_on_delivery", "accept_terms": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("/order/", response.url)
        self.assertEqual(Order.objects.get().items.get().product, self.product)

    def test_guide_returns_only_published_match(self):
        response = self.client.post(reverse("guide"), data='{"message":"Nova AMOLED"}', content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)


class AccountCouponAndSeoTests(PublishedProductMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(username="nexora-user", email="user@example.com", password="safe-pass-123")

    def test_coupon_and_address_cabinet_flow(self):
        coupon = Coupon.objects.create(code="SAVE10", discount_percent=10)
        self.client.post(reverse("add", args=[self.product.pk]), {"quantity": 1})
        self.client.post(reverse("apply_coupon"), {"coupon_code": coupon.code})
        self.assertEqual(self.client.session["coupon_id"], coupon.pk)
        self.client.force_login(self.user)
        response = self.client.post(reverse("add_address"), {
            "title": "Office", "full_name": "Test User", "phone": "555-1234",
            "city": "Tbilisi", "address_line": "123 Rustaveli Ave", "postal_code": "0108", "is_default": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(UserAddress.objects.get(user=self.user).is_default)
        self.assertContains(self.client.get(reverse("cabinet")), "123 Rustaveli Ave")

    def test_pdp_shows_variants_specs_and_json_ld(self):
        self.product.variants.create(name="256 GB", sku="NOVA-X-256", storage="256 GB", stock_quantity=2)
        response = self.client.get(reverse("product", args=[self.product.slug]))
        self.assertContains(response, "256 GB")
        self.assertContains(response, "Ram")
        self.assertContains(response, "application/ld+json")

    def test_robots_sitemap_and_social_metadata(self):
        robots = self.client.get(reverse("robots_txt"))
        self.assertEqual(robots.headers["Content-Type"], "text/plain")
        self.assertContains(robots, "Disallow: /admin/")
        sitemap = self.client.get(reverse("sitemap_xml"))
        self.assertEqual(sitemap.headers["Content-Type"], "application/xml")
        self.assertContains(sitemap, self.product.slug)
        home = self.client.get(reverse("home"))
        self.assertContains(home, 'property="og:title"')
        self.assertContains(home, 'rel="icon"')

    def test_three_language_routes_render(self):
        for path in ("/", "/en/", "/ru/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
