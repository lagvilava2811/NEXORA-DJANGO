from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator


ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "ogg"}
ALLOWED_VIDEO_CONTENT_TYPES = {"video/mp4", "video/webm", "video/ogg", "video/quicktime"}


def validate_video_upload(upload):
    """Allow only small, recognizable browser-playable video containers."""
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


class Category(models.Model):
    name_ka = models.CharField(max_length=80, blank=True)
    name_en = models.CharField(max_length=80, blank=True)
    name_ru = models.CharField(max_length=80, blank=True)
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    parent_category = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="subcategories")
    image = models.URLField(blank=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    seo_title = models.CharField(max_length=150, blank=True)
    seo_description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    @property
    def localized_name(self):
        from django.utils.translation import get_language
        lang = get_language()
        val = getattr(self, f"name_{lang}", "")
        return val if val else self.name


class Brand(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    logo = models.URLField(blank=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    is_featured = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def published(self):
        return (
            self.filter(
                is_active=True,
                is_published=True,
                status="active",
                media__media_type="image",
                media__is_primary=True,
                media__is_verified=True,
                media__image_file__isnull=False,
            )
            .exclude(media__image_file="")
            .distinct()
        )

    def storefront(self):
        return self.published().select_related("category", "primary_category", "brand_obj").prefetch_related("media", "variants")

class Product(models.Model):
    objects = ProductQuerySet.as_manager()
    brand_obj = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products_link")
    brand = models.CharField(max_length=80, default="Nexora")
    primary_category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="primary_products", null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    categories = models.ManyToManyField(Category, related_name="categorized_products", blank=True)

    name_ka = models.CharField(max_length=150, blank=True)
    name_en = models.CharField(max_length=150, blank=True)
    name_ru = models.CharField(max_length=150, blank=True)
    name = models.CharField(max_length=150)
    external_id = models.CharField(max_length=32, null=True, blank=True, unique=True, db_index=True)

    slug = models.SlugField(unique=True)
    sku = models.CharField(max_length=64, default="TEMP", unique=True)
    barcode = models.CharField(max_length=64, blank=True)
    short_description = models.TextField(blank=True)
    full_description = models.TextField(blank=True)
    short_description_ka = models.TextField(blank=True)
    short_description_en = models.TextField(blank=True)
    short_description_ru = models.TextField(blank=True)
    full_description_ka = models.TextField(blank=True)
    full_description_en = models.TextField(blank=True)
    full_description_ru = models.TextField(blank=True)
    description = models.TextField()

    warranty_months = models.PositiveIntegerField(default=24)
    specs = models.JSONField(default=dict, blank=True)
    compatibility = models.JSONField(default=list, blank=True, help_text="List of compatible product SKUs")
    whats_in_box = models.JSONField(default=list, blank=True, help_text="List of items included in box")

    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax_class = models.CharField(default="standard", max_length=32)

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("active", "Active"),
        ("archived", "Archived"),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    is_featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=True)
    is_best_seller = models.BooleanField(default=False)
    is_refurbished = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False, help_text="Only published products with verified images are shown")

    rating_average = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    review_count = models.PositiveIntegerField(default=0)

    image = models.URLField(blank=True)
    source_url = models.URLField(blank=True, help_text="Official product page URL")
    image_licence = models.CharField(max_length=255, blank=True, help_text="Image licence/permission note")
    stock = models.PositiveIntegerField(default=20)

    seo_title = models.CharField(max_length=150, blank=True)
    seo_description = models.TextField(blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product", args=[self.slug])

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def display_image(self):
        verified = sorted(
            (
                media for media in self.media.all()
                if media.media_type == "image" and media.is_verified and media.image_file
            ),
            key=lambda media: (not media.is_primary, media.display_order, media.pk or 0),
        )
        if verified:
            return verified[0].image_file.url
        if not self.is_published:
            fallback = self.media.filter(media_type="image", is_verified=True).exclude(external_url="").first()
            if fallback and fallback.external_url:
                return fallback.external_url
            return self.image
        return ""

    @property
    def gallery_images(self):
        """Return all verified gallery images for this product."""
        return self.media.filter(
            media_type="image", is_verified=True
        ).order_by("-is_primary", "display_order")

    @property
    def has_verified_image(self):
        media = self.media.filter(
            media_type="image", is_verified=True, is_primary=True, image_file__isnull=False
        ).exclude(image_file="").first()
        return bool(media and media.image_file and media.image_file.storage.exists(media.image_file.name))

    @property
    def publishability_issues(self):
        issues = []
        if not self.is_active or self.status != "active":
            issues.append("Product is not active")
        if not self.has_verified_image:
            issues.append("A verified local primary image is required")
        verified_gallery_count = self.media.filter(media_type="image", is_verified=True).exclude(image_file="").count()
        if verified_gallery_count < 4:
            issues.append("At least four verified local gallery images are required")
        return issues

    @property
    def can_publish(self):
        return not self.publishability_issues

    @property
    def discount_percent(self):
        return round((1 - self.price / self.compare_at_price) * 100) if self.compare_at_price and self.compare_at_price > self.price else 0

    @property
    def localized_name(self):
        from django.utils.translation import get_language
        lang = get_language()
        val = getattr(self, f"name_{lang}", "")
        return val if val else self.name

    @property
    def localized_description(self):
        from django.utils.translation import get_language
        lang = get_language() or "en"
        value = getattr(self, f"full_description_{lang}", "")
        if not value:
            value = getattr(self, f"short_description_{lang}", "")
        return value or self.full_description or self.short_description or self.description


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=64, unique=True)
    barcode = models.CharField(max_length=64, blank=True)
    color = models.CharField(max_length=40, blank=True)
    storage = models.CharField(max_length=40, blank=True)
    ram = models.CharField(max_length=40, blank=True)
    size = models.CharField(max_length=40, blank=True)

    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "name"], name="unique_variant_name")]

    @property
    def effective_price(self):
        return self.product.price + self.price_delta

    def __str__(self):
        return f"{self.product.name} · {self.name}"


class ProductMedia(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="media")
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="media")
    MEDIA_TYPE_CHOICES = (
        ("image", "Image"),
        ("video", "Video"),
        ("manual", "Manual/Download"),
    )
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
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(media_type="image", is_primary=True),
                name="one_primary_image_per_product",
            )
        ]

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


class TechnicalSpecification(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="specifications")
    key = models.CharField(max_length=80)
    label_ka = models.CharField(max_length=100)
    label_en = models.CharField(max_length=100)
    label_ru = models.CharField(max_length=100)
    VALUE_TYPE_CHOICES = (
        ("text", "Text"),
        ("number", "Number"),
        ("boolean", "Boolean"),
    )
    value_type = models.CharField(max_length=10, choices=VALUE_TYPE_CHOICES, default="text")
    filterable = models.BooleanField(default=True)
    comparable = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.category.name} - {self.label_en}"


class ProductSpecificationValue(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specification_values")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True, related_name="specification_values")
    specification = models.ForeignKey(TechnicalSpecification, on_delete=models.CASCADE, related_name="values")
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.product.name} - {self.specification.key}: {self.value}"


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.PositiveIntegerField(default=0, help_text="Discount percent (e.g. 10 for 10%)")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Discount amount in currency")
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField(null=True, blank=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Minimum order amount")
    max_uses = models.PositiveIntegerField(default=0, help_text="0 = unlimited")
    max_uses_per_user = models.PositiveIntegerField(default=0, help_text="0 = unlimited per customer")
    times_used = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.code

    @property
    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        if self.max_uses > 0 and self.times_used >= self.max_uses:
            return False
        return True


class GiftCard(models.Model):
    code = models.CharField(max_length=50, unique=True)
    initial_balance = models.DecimalField(max_digits=10, decimal_places=2)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Gift Card {self.code} (₾{self.current_balance})"


class UserAddress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    title = models.CharField(max_length=50, default="Home")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    city = models.CharField(max_length=80, default="Tbilisi")
    address_line = models.TextField()
    postal_code = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlists")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlisted_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")

    def __str__(self):
        return f"{self.user.username} → {self.product.name}"


class CompareList(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="compare_lists")
    products = models.ManyToManyField(Product, related_name="in_comparisons")
    created_at = models.DateTimeField(auto_now_add=True)


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    gift_card = models.ForeignKey(GiftCard, on_delete=models.SET_NULL, null=True, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    reference = models.CharField(max_length=16, unique=True)
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField()
    city = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")

    PAYMENT_CHOICES = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    )
    payment_status = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="pending")
    payment_method = models.CharField(max_length=50, blank=True)
    payment_id = models.CharField(max_length=255, blank=True)

    tracking_number = models.CharField(max_length=100, blank=True)
    shipping_carrier = models.CharField(max_length=50, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(max_length=150, blank=True)
    body = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "user")

    def __str__(self):
        return f"{self.user.username} → {self.product.name} ({self.rating}★)"


class ProductRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='product_ratings')
    rating = models.PositiveSmallIntegerField(choices=[(value, value) for value in range(1, 6)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)
        constraints = [
            models.UniqueConstraint(fields=('product', 'user'), name='unique_product_rating_per_user'),
            models.CheckConstraint(condition=models.Q(rating__gte=1, rating__lte=5), name='product_rating_between_1_and_5'),
        ]

    def __str__(self):
        return f'{self.user} → {self.product} ({self.rating}★)'


class ReturnRequest(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="returns")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    REASON_CHOICES = (
        ("defective", "Defective Product"),
        ("wrong_item", "Wrong Item Received"),
        ("changed_mind", "Changed Mind"),
        ("not_as_described", "Not as Described"),
        ("other", "Other"),
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField()
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Return #{self.id} for {self.order.reference}"


class EmailVerification(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_verification')
    code_digest = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    resend_available_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    send_count = models.PositiveSmallIntegerField(default=0)
    send_window_started_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    pending_verification_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ('-created_at',)

    def check_code(self, candidate):
        return bool(self.code_digest) and check_password(str(candidate), self.code_digest)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_locked(self):
        maximum = getattr(settings, 'EMAIL_VERIFICATION_MAX_ATTEMPTS', 5)
        return self.failed_attempts >= maximum


class WarrantyClaim(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="warranty_claims")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    description = models.TextField()
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_review", "In Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("resolved", "Resolved"),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Warranty #{self.id} - {self.product.name}"
