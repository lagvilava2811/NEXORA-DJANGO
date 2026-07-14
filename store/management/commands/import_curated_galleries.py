from __future__ import annotations

import hashlib
import json
import re
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from store.catalog_sources import image_dhash
from store.models import Product, ProductMedia


class Command(BaseCommand):
    help = "Import vetted local gallery photos from sub-agent source reports."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--delay", type=float, default=1.1)
        parser.add_argument("--max-images", type=int, default=4)
        parser.add_argument("--reports", nargs="*", default=[
            "store/data/gallery_sources_phones.json",
            "store/data/gallery_sources_gaming_wearables.json",
            "store/data/gallery_sources_home_audio.json",
        ])

    def handle(self, *args, **options):
        self.apply = options["apply"]
        self.delay = max(0.8, options["delay"])
        self.max_images = max(1, min(options["max_images"], 6))
        self.next_request = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "NEXORA-curated-gallery/1.0", "Accept": "image/avif,image/webp,image/*"})
        groups = self._load_reports(options["reports"])
        completed, failed = 0, []
        for product in Product.objects.published().order_by("pk"):
            rows = groups.get(self._model_key(product.name), [])
            if not rows:
                continue
            try:
                prepared = self._prepare(product, rows)
                if not prepared:
                    raise ValueError("no valid local image from vetted report")
                if self.apply:
                    self._apply(product, prepared)
                completed += 1
                self.stdout.write(f"{product.name}: {len(prepared)} curated photo(s)")
            except Exception as exc:
                failed.append(f"{product.name}: {str(exc).encode('ascii', 'backslashreplace').decode('ascii')}")
        self.stdout.write(self.style.SUCCESS(f"Curated gallery import: {completed} products updated."))
        for message in failed:
            self.stdout.write(self.style.WARNING(message))

    @staticmethod
    def _model_key(value):
        words = re.findall(r"[a-z0-9]+", str(value).casefold())
        ignored = {"apple", "samsung", "google", "microsoft", "sony", "asus", "amazon"}
        return " ".join(word for word in words if word not in ignored)

    def _load_reports(self, reports):
        groups = {}
        for report in reports:
            path = Path(report)
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                source_rows = []
                for product in data.get("products", []):
                    if not product.get("exact_model_match", False):
                        continue
                    for source in product.get("sources", []):
                        source_rows.append({**source, "model": product.get("exact_model", "")})
            elif isinstance(data, list):
                source_rows = data
            else:
                source_rows = []
            for row in source_rows:
                if not isinstance(row, dict):
                    continue
                model = str(row.get("model") or row.get("exact_model") or "").strip()
                image_url = row.get("image_url") or row.get("direct_image_url")
                source_url = row.get("source_url")
                if model and image_url and source_url:
                    groups.setdefault(self._model_key(model), []).append(row)
        return groups
    def _get(self, url):
        for attempt in range(3):
            pause = self.next_request - time.monotonic()
            if pause > 0:
                time.sleep(pause)
            self.next_request = time.monotonic() + self.delay
            try:
                response = self.session.get(url, timeout=(8, 35))
            except requests.RequestException:
                continue
            if response.status_code == 429:
                time.sleep(4 * (attempt + 1))
                continue
            if response.ok:
                return response.content
        raise ValueError("remote image unavailable")

    def _prepare(self, product, rows):
        hashes = set(ProductMedia.objects.exclude(image_sha256="").values_list("image_sha256", flat=True))
        perceptual = set(ProductMedia.objects.exclude(perceptual_hash="").values_list("perceptual_hash", flat=True))
        prepared = []
        for row in rows:
            if len(prepared) >= self.max_images:
                break
            raw = self._get(row["image_url"] or row["direct_image_url"])
            digest = hashlib.sha256(raw).hexdigest()
            if digest in hashes:
                continue
            try:
                with Image.open(BytesIO(raw)) as source:
                    source.load()
                    image = ImageOps.exif_transpose(source).convert("RGB")
                    if max(image.size) < 240 or min(image.size) < 120:
                        continue
                    if max(image.size) < 900:
                        scale = 900 / max(image.size)
                        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
                    image.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
                    phash = image_dhash(image)
                    if phash in perceptual:
                        continue
                    output = BytesIO()
                    image.save(output, "WEBP", quality=90, method=6)
            except (UnidentifiedImageError, OSError):
                continue
            prepared.append({**row, "bytes": output.getvalue(), "sha": digest, "phash": phash})
            hashes.add(digest)
            perceptual.add(phash)
        return prepared

    def _apply(self, product, prepared):
        folder = Path(settings.MEDIA_ROOT) / "product_uploads" / product.sku
        folder.mkdir(parents=True, exist_ok=True)
        legacy = list(product.media.filter(licence_note__icontains="custom-generated"))
        has_real_primary = product.media.filter(is_primary=True, is_verified=True).exclude(licence_note__icontains="custom-generated").exists()
        with transaction.atomic():
            if legacy:
                ProductMedia.objects.filter(pk__in=[media.pk for media in legacy]).delete()
            for index, item in enumerate(prepared, start=1):
                filename = f"curated-{index}.webp"
                path = folder / filename
                path.write_bytes(item["bytes"])
                licence = str(item.get("licence") or item.get("license") or "Wikimedia Commons")
                author = str(item.get("author") or "")
                note = f"{licence} | author: {author}"[:255] if author else licence[:255]
                ProductMedia.objects.create(
                    product=product, media_type="image", image_file=f"product_uploads/{product.sku}/{filename}",
                    source_url=item["source_url"], licence_note=note, image_sha256=item["sha"],
                    perceptual_hash=item["phash"], is_verified=True, is_primary=not has_real_primary and index == 1,
                    display_order=100 + index, alt_text_en=f"{product.name} {item.get('view_label') or 'product view'}",
                    alt_text_ka=f"{product.name} პროდუქტის ხედი", alt_text_ru=f"{product.name}: вид товара",
                )
            product.is_published = product.has_verified_image
            product.save(update_fields=["is_published", "updated_at"])