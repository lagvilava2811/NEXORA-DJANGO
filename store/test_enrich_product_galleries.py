from __future__ import annotations

import html
import json
from io import BytesIO

from django.test import SimpleTestCase
from PIL import Image, ImageDraw

from store.management.commands.enrich_product_galleries import (
    Candidate,
    average_hash,
    extract_bing_candidates,
    hamming_distance,
    is_candidate_relevant,
    prepare_image,
)


def image_bytes(width=1200, height=900, accent=(35, 95, 210)):
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((90, 60, width - 110, height - 70), radius=55, fill=accent)
    draw.rectangle((width // 3, height // 4, width // 3 + 70, height // 2), fill="black")
    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


class GalleryDiscoveryTests(SimpleTestCase):
    def test_bing_iusc_metadata_is_parsed_without_executing_markup(self):
        metadata = {
            "murl": "https://cdn.example.com/xiaomi-14-front.jpg",
            "purl": "https://shop.example.com/xiaomi-14",
            "t": "Xiaomi 14 front product view",
        }
        markup = f'<a class="iusc result" m="{html.escape(json.dumps(metadata), quote=True)}"></a>'
        candidates = extract_bing_candidates(markup)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].download_url, metadata["murl"])
        self.assertEqual(candidates[0].source_url, metadata["purl"])

    def test_exact_model_gate_rejects_icons_and_wrong_models(self):
        valid = Candidate(
            "https://cdn.example.com/xiaomi-14-back.jpg",
            "https://example.com/xiaomi-14",
            "Xiaomi 14 rear product view",
            "Bing Images",
            "Usage rights unverified",
        )
        icon = Candidate(
            "https://cdn.example.com/xiaomi-14-icon.png",
            "https://example.com/xiaomi-14",
            "Xiaomi 14 logo icon",
            "Bing Images",
            "Usage rights unverified",
        )
        wrong = Candidate(
            "https://cdn.example.com/xiaomi-13.jpg",
            "https://example.com/xiaomi-13",
            "Xiaomi 13 product photo",
            "Bing Images",
            "Usage rights unverified",
        )
        self.assertTrue(is_candidate_relevant("Xiaomi 14", valid))
        self.assertFalse(is_candidate_relevant("Xiaomi 14", icon))
        self.assertFalse(is_candidate_relevant("Xiaomi 14", wrong))

    def test_image_validation_enforces_resolution_aspect_and_webp_output(self):
        prepared = prepare_image(image_bytes())
        self.assertEqual((prepared.width, prepared.height), (1200, 900))
        self.assertEqual(prepared.content[:4], b"RIFF")
        self.assertEqual(len(prepared.sha256), 64)
        self.assertEqual(len(prepared.perceptual_hash), 16)
        with self.assertRaises(ValueError):
            prepare_image(image_bytes(899, 1200))
        with self.assertRaises(ValueError):
            prepare_image(image_bytes(2400, 899))

    def test_average_hash_is_stable_for_resized_near_duplicate(self):
        first = Image.open(BytesIO(image_bytes()))
        same = first.resize((1000, 1000))
        self.assertLessEqual(hamming_distance(average_hash(first), average_hash(same)), 2)