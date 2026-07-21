import io
import tempfile
from decimal import Decimal

from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from .models import Category, Product, ProductMedia


def image_upload(name="device.webp", color="navy"):
    stream = io.BytesIO()
    Image.new("RGB", (640, 640), color).save(stream, "WEBP")
    return SimpleUploadedFile(name, stream.getvalue(), content_type="image/webp")


class PublicationContractTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()
        self.category = Category.objects.create(name="Devices", slug="contract-devices")

    def tearDown(self):
        self.settings_override.disable()
        self.media_dir.cleanup()

    def create_product(self, **overrides):
        values = {
            "category": self.category,
            "name": "Verified Device",
            "slug": f"verified-device-{Product.objects.count()}",
            "sku": f"VERIFY-{Product.objects.count():03d}",
            "description": "Exact model",
            "price": Decimal("999.00"),
            "is_active": True,
            "status": "active",
            "is_published": True,
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def attach_verified_media(self, product, digest=None):
        digest = digest or (f"{product.pk:064x}"[-64:])
        return ProductMedia.objects.create(
            product=product,
            media_type="image",
            image_file=image_upload(f"{product.sku}.webp"),
            source_url=f"https://commons.wikimedia.org/wiki/File:{product.sku}.webp",
            source_item_id=f"Q{product.pk}",
            licence_note="CC BY-SA 4.0",
            image_sha256=digest,
            perceptual_hash=f"{product.pk:016x}"[-16:],
            is_verified=True,
            is_primary=True,
            alt_text_en=product.name,
        )

    def test_published_queryset_requires_explicit_publication_and_verified_local_primary(self):
        valid = self.create_product()
        self.attach_verified_media(valid)
        draft = self.create_product(name="Draft", is_published=False)
        self.attach_verified_media(draft)
        no_media = self.create_product(name="No Media")

        self.assertQuerySetEqual(Product.objects.published(), [valid])
        self.assertFalse(no_media.can_publish)
        self.assertIn("verified local primary image", " ".join(no_media.publishability_issues))

    def test_published_product_never_falls_back_to_remote_image(self):
        product = self.create_product(image="https://example.com/placeholder.jpg")
        ProductMedia.objects.create(
            product=product,
            external_url="https://example.com/remote.jpg",
            source_url="https://example.com/source",
            licence_note="Press asset",
            is_verified=True,
            is_primary=True,
        )
        self.assertEqual(product.display_image, "")

    def test_verified_media_validation_requires_local_file_and_provenance(self):
        product = self.create_product(is_published=False)
        media = ProductMedia(product=product, is_verified=True, is_primary=True)
        with self.assertRaises(ValidationError) as error:
            media.full_clean()
        self.assertIn("image_file", error.exception.message_dict)
        self.assertIn("source_url", error.exception.message_dict)
        self.assertIn("licence_note", error.exception.message_dict)

    def test_image_sha256_is_unique(self):
        first = self.create_product()
        second = self.create_product(name="Second")
        digest = "a" * 64
        self.attach_verified_media(first, digest=digest)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.attach_verified_media(second, digest=digest)

    def test_local_verified_media_is_the_display_image(self):
        product = self.create_product()
        media = self.attach_verified_media(product)
        self.assertEqual(product.display_image, media.image_file.url)
        self.assertTrue(product.has_verified_image)