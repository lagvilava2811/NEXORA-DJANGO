import io
import tempfile
from decimal import Decimal

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from .models import Category, Product, ProductMedia


def image_upload(name, size, color):
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, "WEBP")
    return SimpleUploadedFile(name, stream.getvalue(), content_type="image/webp")


class CatalogAuditCommandTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.media_dir.cleanup()

    def test_strict_audit_fails_when_minimum_catalog_is_not_met(self):
        with self.assertRaises(CommandError) as error:
            call_command(
                "audit_catalog",
                strict=True,
                minimum_products=1,
                minimum_images=1,
            )

        self.assertIn("Catalog audit failed", str(error.exception))

    def test_strict_audit_accepts_a_complete_small_catalog(self):
        category = Category.objects.create(name="Phones", slug="audit-phones")
        product = Product.objects.create(
            category=category,
            name="Audit Phone",
            name_ka="Audit phone KA",
            name_en="Audit Phone",
            name_ru="Audit phone RU",
            slug="audit-phone",
            sku="AUDIT-PHONE-001",
            description="Complete product",
            short_description_ka="Complete description KA",
            short_description_en="Complete description",
            short_description_ru="Complete description RU",
            specs={"display": "6.7 inch"},
            price=Decimal("999.00"),
            is_active=True,
            is_published=True,
            status="active",
            review_count=0,
        )
        media_values = (
            ("primary.webp", (1200, 900), "navy", True, "0" * 16),
            ("secondary.webp", (1000, 720), "white", False, "f" * 16),
        )
        for index, (name, size, color, is_primary, perceptual_hash) in enumerate(media_values):
            ProductMedia.objects.create(
                product=product,
                media_type="image",
                image_file=image_upload(name, size, color),
                source_url=f"https://example.com/{name}",
                licence_note="Manufacturer press asset",
                image_sha256=f"{index + 1:064x}",
                perceptual_hash=perceptual_hash,
                is_verified=True,
                is_primary=is_primary,
                display_order=index,
                alt_text_ka=f"{product.name_ka} view {index + 1}",
                alt_text_en=f"{product.name_en} view {index + 1}",
                alt_text_ru=f"{product.name_ru} view {index + 1}",
            )

        output = io.StringIO()
        call_command(
            "audit_catalog",
            strict=True,
            minimum_products=1,
            minimum_images=2,
            stdout=output,
        )

        self.assertIn("PASS", output.getvalue())
        self.assertIn("audit-phones: 1", output.getvalue())
