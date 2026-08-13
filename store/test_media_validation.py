import io

from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase


def image_upload(name="product.webp", size=(1200, 1200)):
    stream = io.BytesIO()
    Image.new("RGB", size, "navy").save(stream, "WEBP", quality=85)
    return SimpleUploadedFile(name, stream.getvalue(), content_type="image/webp")


class ProductImageUploadValidationTests(SimpleTestCase):
    def test_accepts_a_real_web_optimized_product_image(self):
        from store.models import validate_image_upload

        validate_image_upload(image_upload())

    def test_rejects_spoofed_image_content(self):
        from store.models import validate_image_upload

        upload = SimpleUploadedFile("product.webp", b"not an image", content_type="image/webp")
        with self.assertRaises(ValidationError):
            validate_image_upload(upload)

    def test_rejects_oversized_images_before_storage(self):
        from store.models import validate_image_upload

        upload = SimpleUploadedFile(
            "product.webp",
            b"0" * (5 * 1024 * 1024 + 1),
            content_type="image/webp",
        )
        with self.assertRaisesMessage(ValidationError, "5 MB"):
            validate_image_upload(upload)
