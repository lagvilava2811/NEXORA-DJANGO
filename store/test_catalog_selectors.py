from decimal import Decimal

from django.test import SimpleTestCase


class CatalogFilterParsingTests(SimpleTestCase):
    def test_normalizes_and_bounds_public_query_parameters(self):
        from store.selectors.catalog import CatalogFilters

        filters = CatalogFilters.from_query(
            {
                "q": "  gaming laptop  ",
                "category": "laptops",
                "brand": "  ASUS  ",
                "min_price": "999.99",
                "max_price": "2500",
                "min_rating": "4.5",
                "in_stock": "1",
                "discount": "1",
                "sort": "price-desc",
            }
        )

        self.assertEqual(filters.query, "gaming laptop")
        self.assertEqual(filters.category, "laptops")
        self.assertEqual(filters.brand, "ASUS")
        self.assertEqual(filters.min_price, Decimal("999.99"))
        self.assertEqual(filters.max_price, Decimal("2500"))
        self.assertEqual(filters.min_rating, Decimal("4.5"))
        self.assertTrue(filters.in_stock)
        self.assertTrue(filters.discount)
        self.assertEqual(filters.ordering, "-price")

    def test_rejects_invalid_ranges_and_unknown_sort_values(self):
        from store.selectors.catalog import CatalogFilters

        filters = CatalogFilters.from_query(
            {
                "min_price": "-1",
                "max_price": "not-a-number",
                "min_rating": "6",
                "sort": "drop-table",
            }
        )

        self.assertIsNone(filters.min_price)
        self.assertIsNone(filters.max_price)
        self.assertIsNone(filters.min_rating)
        self.assertEqual(filters.sort, "featured")
        self.assertEqual(filters.ordering, "-is_featured")

    def test_caps_search_and_slug_like_values(self):
        from store.selectors.catalog import CatalogFilters

        filters = CatalogFilters.from_query(
            {"q": "x" * 200, "category": "c" * 140, "brand": "b" * 140}
        )

        self.assertEqual(len(filters.query), 120)
        self.assertEqual(len(filters.category), 100)
        self.assertEqual(len(filters.brand), 100)
