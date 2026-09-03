"""Stable Django model registry and backward-compatible public import surface.

Domain implementations live in ``store.model_components``.  Keeping this
module means existing migrations and ``from store.models import Product``
imports continue to work without a database schema change.
"""

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from .model_components.catalog import Brand, Category, Product, ProductQuerySet
from .model_components.product_details import ProductSpecificationValue, ProductVariant, TechnicalSpecification


ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "ogg"}
ALLOWED_VIDEO_CONTENT_TYPES = {"video/mp4", "video/webm", "video/ogg", "video/quicktime"}


def validate_video_upload(upload):
    """Allow only small, recognizable browser-playable video containers.

    This callable intentionally stays at ``store.models.validate_video_upload``
    because an applied migration imports it from this exact path.
    """
    filename = getattr(upload, "name", "")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValidationError("Upload a valid video file (MP4, WebM, MOV, or OGG).")
    content_type = getattr(upload, "content_type", "")
    if content_type and content_type.lower() not in ALLOWED_VIDEO_CONTENT_TYPES:
        raise ValidationError("Upload a valid video content type.")
    try:
        position = upload.tell()
        header = upload.read(32)
        upload.seek(position)
    except (AttributeError, OSError):
        return
    is_iso_video = len(header) >= 8 and header[4:8] == b"ftyp"
    is_webm = header.startswith(b"\x1aE\xdf\xa3")
    is_ogg = header.startswith(b"OggS")
    if not (is_iso_video or is_webm or is_ogg):
        raise ValidationError("Upload a valid video file.")


class ProductMedia(models.Model):
    """Media remains here with its migration-pinned validator in this pass."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="media")
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="media")
    MEDIA_TYPE_CHOICES = (("image", "Image"), ("video", "Video"), ("manual", "Manual/Download"))
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default="image")
    image_file = models.ImageField(upload_to="product_uploads/", blank=True, null=True, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    video_file = models.FileField(upload_to="product_uploads/", blank=True, null=True, validators=[validate_video_upload])
    external_url = models.URLField(blank=True, null=True)
    source_url = models.URLField(blank=True, null=True)
    source_item_id = models.CharField(max_length=32, blank=True)
    image_sha256 = models.CharField(max_length=64, null=True, blank=True, unique=True, db_index=True)
    perceptual_hash = models.CharField(max_length=16, blank=True, db_index=True)
    licence_note = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False)
    alt_text_ka = models.CharField(max_length=200, blank=True)
    alt_text_en = models.CharField(max_length=200, blank=True)
    alt_text_ru = models.CharField(max_length=200, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product"], condition=models.Q(media_type="image", is_primary=True), name="one_primary_image_per_product")]

    def clean(self):
        super().clean()
        errors = {}
        if self.is_verified:
            if not self.image_file:
                errors["image_file"] = "Verified product media must be stored locally."
            if not self.source_url:
                errors["source_url"] = "Verified product media requires a provenance URL."
            if not self.licence_note:
                errors["licence_note"] = "Verified product media requires licence metadata."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.product.name} media ({self.media_type})"

    @property
    def localized_alt(self):
        from django.utils.translation import get_language
        language = (get_language() or "en").split("-", 1)[0]
        return getattr(self, f"alt_text_{language}", "") or self.product.localized_name


from .model_components.account_security import AccountDeletionRequest, EmailVerification, PasswordResetCode
from .model_components.cart import Cart, CartItem
from .model_components.customer import CompareList, UserAddress, Wishlist
from .model_components.feedback import ProductRating, Review
from .model_components.orders import Order, OrderItem, ReturnRequest, WarrantyClaim
from .model_components.promotions import Coupon, GiftCard


__all__ = [
    "ALLOWED_VIDEO_CONTENT_TYPES", "ALLOWED_VIDEO_EXTENSIONS", "validate_video_upload",
    "Category", "Brand", "ProductQuerySet", "Product", "ProductVariant", "ProductMedia",
    "TechnicalSpecification", "ProductSpecificationValue", "Coupon", "GiftCard", "UserAddress",
    "Wishlist", "Cart", "CartItem", "CompareList", "Order", "OrderItem", "Review",
    "ProductRating", "ReturnRequest", "EmailVerification", "PasswordResetCode",
    "AccountDeletionRequest", "WarrantyClaim",
]
