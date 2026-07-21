from PIL import Image
from django.test import SimpleTestCase

from .catalog_sources import (
    CATEGORY_SOURCES,
    build_sparql,
    commons_filename,
    deterministic_price,
    entity_id,
    hamming_distance,
    image_dhash,
    model_match_score,
    model_media_matches,
    normalise_file_title,
    round_robin,
    safe_brand,
    variant_blueprints,
)


class CatalogSourceTests(SimpleTestCase):
    def test_source_pool_is_large_and_diverse(self):
        self.assertGreaterEqual(sum(source.candidate_limit for source in CATEGORY_SOURCES), 1500)
        self.assertGreaterEqual(len(CATEGORY_SOURCES), 12)
        self.assertEqual(len({source.class_id for source in CATEGORY_SOURCES}), len(CATEGORY_SOURCES))

    def test_sparql_requires_exact_model_class_and_image_claim(self):
        source = CATEGORY_SOURCES[0]
        query = build_sparql(source)
        self.assertIn(f"wdt:P31 wd:{source.class_id}", query)
        self.assertIn("wdt:P18", query)
        self.assertIn(f"LIMIT {source.candidate_limit}", query)

    def test_entity_and_commons_identifiers_are_strictly_parsed(self):
        self.assertEqual(entity_id("http://www.wikidata.org/entity/Q122442399"), "Q122442399")
        self.assertEqual(
            commons_filename("http://commons.wikimedia.org/wiki/Special:FilePath/Apple%20iPhone.jpg"),
            "Apple iPhone.jpg",
        )
        self.assertEqual(normalise_file_title("File:Apple_iPhone.jpg"), "apple iphone.jpg")
        with self.assertRaises(ValueError):
            entity_id("https://example.com/not-an-item")

    def test_model_media_gate_rejects_related_but_wrong_hardware(self):
        wrong = "INTEL CORE ULTRA 7 265K product photo.png"
        self.assertFalse(model_media_matches("Intel Core Ultra 9 285K", wrong))
        self.assertEqual(model_match_score("System76 Darter Pro 11", "System76 product darp10.webp"), 0.0)
        self.assertTrue(model_media_matches("Surface Pro 4", "SurfacePro4mitTypeCover.jpg"))
        self.assertTrue(model_media_matches("Fujifilm X-T30 III", "Fujifilm X-T30 III 25 oct 2025a.jpg"))
    def test_brand_fallback_uses_known_product_families(self):
        self.assertEqual(safe_brand("iPhone 15 Pro", None), "Apple")
        self.assertEqual(safe_brand("Samsung Galaxy S24", None), "Samsung")
        self.assertEqual(safe_brand("EOS camera", "Canon Inc."), "Canon Inc.")

    def test_prices_and_variants_are_deterministic(self):
        source = CATEGORY_SOURCES[0]
        self.assertEqual(deterministic_price("Q1", source), deterministic_price("Q1", source))
        self.assertGreaterEqual(deterministic_price("Q1", source), source.min_price)
        self.assertEqual(len(variant_blueprints("smartphones")), 3)
        self.assertEqual(len(variant_blueprints("mice")), 2)

    def test_perceptual_hash_is_stable_and_comparable(self):
        image = Image.new("RGB", (64, 64), "white")
        copy = image.copy()
        left = image_dhash(image)
        right = image_dhash(copy)
        self.assertEqual(left, right)
        self.assertEqual(hamming_distance(left, right), 0)

    def test_round_robin_prevents_one_category_from_dominating(self):
        groups = {
            "smartphones": [{"id": 1}, {"id": 2}, {"id": 3}],
            "cameras": [{"id": 4}, {"id": 5}],
        }
        self.assertEqual([item["id"] for item in round_robin(groups)], [1, 4, 2, 5, 3])