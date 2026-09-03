from django.db import models
from django.urls import reverse
from django.utils import timezone


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

    def search(self, query):
        """Search the catalogue with PostgreSQL ranking and a portable fallback."""
        query = (query or "").strip()[:120]
        if not query:
            return self

        from django.db import connection

        if connection.vendor == "postgresql":
            from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramWordSimilarity

            search_query = SearchQuery(query, config="simple", search_type="websearch")
            vector = SearchVector("search_document", config="simple")
            return (
                self.annotate(
                    search_vector=vector,
                    search_rank=SearchRank(vector, search_query),
                    search_similarity=TrigramWordSimilarity(query, "search_document"),
                )
                .filter(
                    models.Q(search_vector=search_query)
                    | models.Q(search_document__trigram_word_similar=query)
                )
                .order_by("-search_rank", "-search_similarity", "-is_featured", "name", "pk")
            )

        return self.filter(
            models.Q(name__icontains=query)
            | models.Q(name_ka__icontains=query)
            | models.Q(name_en__icontains=query)
            | models.Q(name_ru__icontains=query)
            | models.Q(description__icontains=query)
            | models.Q(short_description__icontains=query)
            | models.Q(full_description__icontains=query)
            | models.Q(brand__icontains=query)
            | models.Q(sku__icontains=query)
        )


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
    STATUS_CHOICES = (("draft", "Draft"), ("active", "Active"), ("archived", "Archived"))
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
    search_document = models.TextField(blank=True, editable=False, default="")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def build_search_document(self):
        return " ".join(str(value).strip() for value in (self.name, self.name_ka, self.name_en, self.name_ru, self.brand, self.sku, self.short_description, self.full_description, self.description) if value)

    def save(self, *args, **kwargs):
        self.search_document = self.build_search_document()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"search_document"}
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("product", args=[self.slug])

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def display_image(self):
        verified = sorted((media for media in self.media.all() if media.media_type == "image" and media.is_verified and media.image_file), key=lambda media: (not media.is_primary, media.display_order, media.pk or 0))
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
        return self.media.filter(media_type="image", is_verified=True).order_by("-is_primary", "display_order")

    @property
    def has_verified_image(self):
        media = self.media.filter(media_type="image", is_verified=True, is_primary=True, image_file__isnull=False).exclude(image_file="").first()
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

