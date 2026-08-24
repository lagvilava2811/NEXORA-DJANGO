from decimal import Decimal

from django.core.paginator import Paginator
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, ProductMedia


class ShopPaginationTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Phones", slug="phones")
        Product.objects.bulk_create([
            Product(
                category=category,
                primary_category=category,
                name=f"Phone {number}",
                slug=f"phone-{number}",
                sku=f"PAGE-{number:03d}",
                description="Pagination fixture",
                price=Decimal("100.00"),
                stock=4,
                is_active=True,
                is_published=True,
                status="active",
            )
            for number in range(50)
        ])
        products = list(Product.objects.order_by("pk"))
        ProductMedia.objects.bulk_create([
            ProductMedia(
                product=product,
                media_type="image",
                image_file=f"product_uploads/test/{product.sku}.webp",
                is_verified=True,
                is_primary=True,
                source_url="https://example.com/source",
                source_item_id=f"test-{product.pk}",
                licence_note="Test fixture",
                image_sha256=f"{product.pk:064x}",
                perceptual_hash=f"{product.pk:016x}",
            )
            for product in products
        ])

    def test_elided_range_uses_two_neighbours_and_two_ends(self):
        paginator = Paginator(range(1, 1001), 1)
        self.assertEqual(
            list(paginator.get_elided_page_range(500, on_each_side=2, on_ends=2)),
            [1, 2, "…", 498, 499, 500, 501, 502, "…", 999, 1000],
        )

    def test_shop_uses_reusable_pagination_and_preserves_query_state(self):
        response = self.client.get(reverse("shop"), {
            "category": "phones", "q": "Phone", "sort": "price-asc", "page": 2,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "store/pagination.html")
        self.assertContains(response, "category=phones&amp;q=Phone&amp;sort=price-asc&amp;page=1")
        self.assertContains(response, "aria-current=\"page\">2")
