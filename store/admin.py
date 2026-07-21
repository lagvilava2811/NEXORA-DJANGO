from django.contrib import admin
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Brand, Category, CompareList, Coupon, EmailVerification, GiftCard, Order, OrderItem, Product,
    ProductMedia, ProductRating, ProductSpecificationValue, ProductVariant, ReturnRequest, Review,
    TechnicalSpecification, UserAddress, WarrantyClaim, Wishlist,
)

admin.site.site_header = "NEXORA CONTROL ROOM"
admin.site.site_title = "NEXORA Admin"
admin.site.index_title = "Commerce operations"


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("name", "sku", "color", "storage", "ram", "size", "price_delta", "stock_quantity", "reserved_quantity", "is_active")
    readonly_fields = ("reserved_quantity",)


class MediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 0
    fields = ("media_type", "image_file", "source_url", "licence_note", "is_verified", "is_primary", "display_order", "image_sha256")
    readonly_fields = ("image_sha256",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent_category", "display_order", "is_active", "product_count")
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active", "parent_category")
    search_fields = ("name", "name_ka", "name_en", "name_ru", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("display_order", "name")
    list_select_related = ("parent_category",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_product_count=Count("products", distinct=True))

    @admin.display(description="Products", ordering="_product_count")
    def product_count(self, obj):
        return obj._product_count


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "product_count", "is_featured", "display_order")
    list_editable = ("is_featured", "display_order")
    search_fields = ("name", "slug", "website")
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_product_count=Count("products_link", distinct=True))

    @admin.display(description="Products", ordering="_product_count")
    def product_count(self, obj):
        return obj._product_count


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("preview", "name", "brand_obj", "sku", "primary_category", "price", "stock", "is_published", "status")
    list_filter = ("is_published", "status", "is_active", "is_featured", "is_new", "is_best_seller", "primary_category", "brand_obj")
    search_fields = ("name", "name_ka", "name_en", "name_ru", "sku", "external_id", "brand", "description")
    list_editable = ("price", "stock", "is_published", "status")
    list_select_related = ("brand_obj", "primary_category", "category")
    autocomplete_fields = ("brand_obj", "primary_category", "category", "categories")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = (
        'preview_large', 'created_at', 'updated_at', 'publication_status',
        'rating', 'rating_average', 'rating_count', 'review_count',
    )
    inlines = (VariantInline, MediaInline)
    save_on_top = True
    ordering = ("-created_at",)
    fieldsets = (
        ("Identity", {"fields": ("external_id", "name", "slug", "sku", "barcode", "brand_obj", "brand", "primary_category", "category", "categories")}),
        ("Translations", {"fields": ("name_ka", "name_en", "name_ru", "short_description_ka", "short_description_en", "short_description_ru", "full_description_ka", "full_description_en", "full_description_ru"), "classes": ("collapse",)}),
        ("Commercial", {"fields": ("price", "compare_at_price", "cost_price", "tax_class", "stock", "warranty_months")}),
        ("Product intelligence", {"fields": ("short_description", "description", "full_description", "specs", "compatibility", "whats_in_box", "source_url", "image_licence", "image", "preview_large")}),
        ('Publishing', {'fields': ('status', 'is_active', 'is_published', 'publication_status', 'is_featured', 'is_new', 'is_best_seller', 'is_refurbished', 'rating', 'rating_average', 'rating_count', 'review_count')}),
        ("SEO", {"fields": ("seo_title", "seo_description"), "classes": ("collapse",)}),
        ("Audit", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Preview")
    def preview(self, obj):
        return self._image(obj, 44)

    @admin.display(description="Image")
    def preview_large(self, obj):
        return self._image(obj, 240)

    def _image(self, obj, size):
        source = obj.display_image
        if not source:
            return "No verified local image"
        return format_html('<img src="{}" alt="" style="width:{}px;height:{}px;object-fit:contain;border-radius:10px;background:#f4f6fb;padding:5px">', source, size, size)

    @admin.display(description="Publication contract")
    def publication_status(self, obj):
        return "Ready" if obj.can_publish else "; ".join(obj.publishability_issues)


@admin.register(ProductMedia)
class ProductMediaAdmin(admin.ModelAdmin):
    list_display = ("thumbnail", "product", "source_item_id", "media_type", "is_primary", "is_verified", "has_provenance", "image_sha256_short")
    list_filter = ("media_type", "is_primary", "is_verified")
    search_fields = ("product__name", "product__sku", "source_item_id", "source_url", "image_sha256")
    autocomplete_fields = ("product", "variant")
    readonly_fields = ("image_sha256", "perceptual_hash")
    list_select_related = ("product", "variant")
    actions = ("mark_verified", "mark_unverified")

    @admin.display(description="Preview")
    def thumbnail(self, obj):
        if not obj.image_file:
            return "—"
        return format_html('<img src="{}" alt="" style="width:44px;height:44px;object-fit:contain;background:#f4f6fb;border-radius:8px">', obj.image_file.url)

    @admin.display(description="Source complete", boolean=True)
    def has_provenance(self, obj):
        return bool(obj.source_url and obj.licence_note and obj.source_item_id)

    @admin.display(description="SHA-256")
    def image_sha256_short(self, obj):
        return obj.image_sha256[:12] if obj.image_sha256 else "—"

    @admin.action(description="Verify selected complete media")
    def mark_verified(self, request, queryset):
        queryset.exclude(image_file="").exclude(source_url="").exclude(licence_note="").update(is_verified=True)

    @admin.action(description="Unverify selected media")
    def mark_unverified(self, request, queryset):
        queryset.update(is_verified=False)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "name", "effective_price", "stock_quantity", "reserved_quantity", "is_active")
    list_editable = ("stock_quantity", "is_active")
    list_filter = ("is_active", "product__primary_category")
    search_fields = ("sku", "barcode", "name", "product__name")
    autocomplete_fields = ("product",)
    list_select_related = ("product",)


@admin.register(TechnicalSpecification)
class TechnicalSpecificationAdmin(admin.ModelAdmin):
    list_display = ("key", "label_en", "category", "value_type", "filterable", "comparable")
    list_editable = ("filterable", "comparable")
    list_filter = ("category", "value_type")
    search_fields = ("key", "label_ka", "label_en", "label_ru")
    autocomplete_fields = ("category",)


@admin.register(ProductSpecificationValue)
class ProductSpecificationValueAdmin(admin.ModelAdmin):
    list_display = ("product", "specification", "value", "variant")
    search_fields = ("product__name", "product__sku", "specification__key", "value")
    autocomplete_fields = ("product", "variant", "specification")
    list_select_related = ("product", "variant", "specification")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_percent", "discount_amount", "min_order_amount", "times_used", "max_uses", "max_uses_per_user", "is_active", "valid_now")
    list_editable = ("is_active",)
    list_filter = ("is_active", "valid_from", "valid_to")
    search_fields = ("code",)

    @admin.display(description="Valid now", boolean=True)
    def valid_now(self, obj):
        now = timezone.now()
        return obj.is_valid and obj.valid_from <= now


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = ("code", "initial_balance", "current_balance", "is_active", "expires_at")
    list_editable = ("is_active",)
    search_fields = ("code",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "variant", "quantity", "unit_price", "line_total")
    def has_add_permission(self, request, obj=None): return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "full_name", "email", "status", "payment_status", "total", "created_at")
    list_filter = ("status", "payment_status", "payment_method", "created_at")
    search_fields = ("reference", "full_name", "email", "phone", "payment_id", "tracking_number")
    list_select_related = ("user", "coupon", "gift_card")
    readonly_fields = ("reference", "user", "coupon", "gift_card", "full_name", "email", "phone", "address", "city", "postal_code", "subtotal", "shipping_cost", "tax_amount", "discount_amount", "total", "payment_id", "created_at", "updated_at")
    fields = ("reference", "user", "status", "payment_status", "payment_method", "payment_id", "full_name", "email", "phone", "address", "city", "postal_code", "subtotal", "shipping_cost", "tax_amount", "discount_amount", "total", "coupon", "gift_card", "tracking_number", "shipping_carrier", "estimated_delivery", "notes", "created_at", "updated_at")
    inlines = (OrderItemInline,)
    date_hierarchy = "created_at"
    def has_add_permission(self, request): return False


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "is_verified_purchase", "is_approved", "created_at")
    list_editable = ("is_approved",)
    list_filter = ("rating", "is_verified_purchase", "is_approved", "created_at")
    search_fields = ("product__name", "user__username", "title", "body")


@admin.register(ProductRating)
class ProductRatingAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'updated_at')
    list_filter = ('rating', 'updated_at')
    search_fields = ('product__name', 'product__sku', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "full_name", "city", "phone", "is_default")
    search_fields = ("user__username", "user__email", "full_name", "phone", "address_line")
    list_filter = ("city", "is_default")


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'state', 'expires_at', 'failed_attempts', 'send_count', 'updated_at')
    list_filter = ('verified_at', 'expires_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = (
        'user', 'state', 'expires_at', 'resend_available_at', 'failed_attempts',
        'send_count', 'send_window_started_at', 'verified_at', 'created_at', 'updated_at',
    )
    fields = readonly_fields
    list_select_related = ('user',)

    @admin.display(description='Status')
    def state(self, obj):
        if obj.verified_at:
            return 'Verified'
        if obj.is_locked:
            return 'Locked'
        if obj.is_expired:
            return 'Expired'
        return 'Pending'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Wishlist)
admin.site.register(CompareList)
admin.site.register(ReturnRequest)
admin.site.register(WarrantyClaim)
