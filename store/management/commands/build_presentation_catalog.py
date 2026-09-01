"""Build the portable, media-backed catalogue used by the public Render demo.

The source database is larger and contains historical devices.  This command
creates a reproducible presentation subset: the current curated collection is
always retained, then newer Wikidata-backed products are selected by release
year.  Every exported product has a verified local *primary* image, so the
hosted shop never renders an empty product card.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError

from store.models import Brand, Category, Product, ProductMedia


MINIMUM_CURRENT_YEAR = 2017


class Command(BaseCommand):
    help = "Build a portable modern NEXORA product fixture and local-media ZIP."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=200)

    def handle(self, *args, **options):
        requested_count = options["count"]
        if requested_count < 1:
            raise CommandError("--count must be positive")

        release_years = self._release_years()
        products, primary_media = self._eligible_products()

        curated = [product for product in products if not product.external_id]
        current = [
            product for product in products
            if release_years.get(product.external_id, 0) >= MINIMUM_CURRENT_YEAR
        ]
        fallback = [
            product for product in products
            if product not in curated and product not in current
        ]
        current.sort(
            key=lambda product: (
                -release_years.get(product.external_id, 0),
                product.category.slug,
                product.name.casefold(),
            )
        )
        # The fixture has 199 current/2017+ items. If a strict 200th item is
        # requested, take the newest available fallback rather than whichever
        # historical item happens to sort first alphabetically.
        fallback.sort(
            key=lambda product: (
                -release_years.get(product.external_id, 0),
                product.category.slug,
                product.name.casefold(),
            )
        )

        selected = []
        seen = set()
        for product in curated + current + fallback:
            if product.pk in seen:
                continue
            selected.append(product)
            seen.add(product.pk)
            if len(selected) == requested_count:
                break
        if len(selected) < requested_count:
            raise CommandError(
                f"Only {len(selected)} products have verified local primary images; "
                f"cannot build {requested_count}."
            )

        fallback_count = sum(
            1 for product in selected
            if product not in curated and release_years.get(product.external_id, 0) < MINIMUM_CURRENT_YEAR
        )
        # The original curated set is the public showcase and keeps its full
        # gallery. The remaining 155 products intentionally carry one verified
        # primary image each: that is enough for a fast, honest catalogue while
        # avoiding a 100MB+ repository payload for 200 x 3 gallery views.
        curated_ids = {product.pk for product in selected if not product.external_id}
        selected_ids = {product.pk for product in selected}
        selected_media = []
        for media in ProductMedia.objects.filter(
            product_id__in=selected_ids, media_type="image", is_verified=True
        ).exclude(image_file="").order_by("product_id", "-is_primary", "display_order", "pk"):
            if not media.image_file or not media.image_file.storage.exists(media.image_file.name):
                continue
            if media.product_id in curated_ids or media.pk == primary_media[media.product_id].pk:
                selected_media.append(media)
        self._write_fixture(selected, selected_media)
        self._write_media_archive(selected_media)

        categories = {product.category.slug for product in selected}
        self.stdout.write(self.style.SUCCESS(
            f"Built {len(selected)} products across {len(categories)} categories "
            f"({fallback_count} pre-{MINIMUM_CURRENT_YEAR} fallback products)."
        ))

    def _release_years(self):
        manifest = Path(settings.BASE_DIR) / "store" / "data" / "wikidata_catalog_manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        years = {}
        for item in data:
            released = str(item.get("released") or "")
            try:
                years[item.get("qid")] = int(released[:4])
            except (TypeError, ValueError):
                continue
        return years

    def _eligible_products(self):
        media_by_product = defaultdict(list)
        media_queryset = ProductMedia.objects.filter(
            media_type="image", is_verified=True, is_primary=True
        ).exclude(image_file="").order_by("product_id", "display_order", "pk")
        for media in media_queryset.select_related("product"):
            if media.image_file and media.image_file.storage.exists(media.image_file.name):
                media_by_product[media.product_id].append(media)

        products = list(
            Product.objects.published().select_related("category", "primary_category", "brand_obj")
            .prefetch_related("categories").order_by("pk")
        )
        products = [product for product in products if media_by_product.get(product.pk)]
        primary_media = {product.pk: media_by_product[product.pk][0] for product in products}
        return products, primary_media

    def _write_fixture(self, products, media_items):
        category_ids = set()
        brand_ids = set()
        for product in products:
            category_ids.add(product.category_id)
            if product.primary_category_id:
                category_ids.add(product.primary_category_id)
            category_ids.update(product.categories.values_list("pk", flat=True))
            if product.brand_obj_id:
                brand_ids.add(product.brand_obj_id)

        objects = [
            *Category.objects.filter(pk__in=category_ids).order_by("pk"),
            *Brand.objects.filter(pk__in=brand_ids).order_by("pk"),
            *products,
            *media_items,
        ]
        serialized = serializers.serialize("json", objects, indent=2)
        root_target = Path(settings.BASE_DIR) / "render_presentation_catalog.json"
        data_target = Path(settings.BASE_DIR) / "store" / "data" / "render_presentation_catalog.json"
        for target in (root_target, data_target):
            target.write_text(serialized, encoding="utf-8")

    def _write_media_archive(self, media_items):
        target = Path(settings.BASE_DIR) / "render_presentation_catalog_media.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for media in media_items:
                source = Path(media.image_file.path)
                archive.write(source, arcname=media.image_file.name.replace("\\", "/"))
