from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from store.catalog_sources import image_dhash, model_match_score, normalise_file_title
from store.models import Product, ProductMedia

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "NEXORA-media-refresh/1.0 (local product gallery builder)"

CURATED_GALLERY_FILES = {
    "SAM-S24U-256-TI": [
        "Samsung-Galaxy-S24-Ultra-Front.jpg",
        "Back view of Samsung Galaxy S24 Ultra Black.jpg",
        "Samsung Galaxy S24 Ultra with retail box, front.jpg",
        "Samsung Galaxy S24 Ultra 03.jpg",
    ],
}


class Command(BaseCommand):
    help = "Replace legacy generated product silhouettes with real, source-tracked Wikimedia product galleries."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write verified galleries to media and database.")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--max-images", type=int, default=4)
        parser.add_argument("--delay", type=float, default=1.25, help="Minimum seconds between remote requests.")
        parser.add_argument("--include-all", action="store_true", help="Refresh all published products, not only legacy generated media.")
        parser.add_argument("--sku", action="append", default=[], help="Refresh a specific SKU; repeatable.")

    def handle(self, *args, **options):
        self.apply = options["apply"]
        self.max_images = max(1, min(options["max_images"], 6))
        self.delay = max(0.8, options["delay"])
        self.next_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

        products = Product.objects.published().prefetch_related("media").order_by("pk")
        if options["sku"]:
            products = products.filter(sku__in=options["sku"])
        if not options["include_all"]:
            products = [
                product for product in products
                if any("custom-generated" in (media.licence_note or "").casefold() for media in product.media.all())
            ]
        else:
            products = list(products)
        if options["limit"]:
            products = products[: options["limit"]]

        completed = 0
        failures = []
        for index, product in enumerate(products, start=1):
            try:
                gallery = self._build_gallery(product)
                if not gallery:
                    raise ValueError("no exact, usable Wikimedia gallery image found")
                if self.apply:
                    self._replace_gallery(product, gallery)
                completed += 1
                self.stdout.write(self.style.SUCCESS(f"[{index}/{len(products)}] {product.name}: {len(gallery[1])} real gallery image(s)"))
            except Exception as exc:
                failures.append(f"{product.sku} {product.name}: {exc}")
                self.stdout.write(self.style.WARNING(f"[{index}/{len(products)}] skipped {product.name}: {exc}"))

        verb = "Replaced" if self.apply else "Validated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {completed}/{len(products)} legacy gallery set(s)."))
        if failures:
            self.stdout.write(self.style.WARNING(f"Skipped {len(failures)} product(s)."))
            for failure in failures[:25]:
                self.stdout.write(self.style.WARNING(f"  {failure}"))

    def _wait(self):
        pause = self.next_request_at - time.monotonic()
        if pause > 0:
            time.sleep(pause)
        self.next_request_at = time.monotonic() + self.delay

    def _request(self, url, *, params=None, stream=False):
        last_error = None
        for attempt in range(3):
            self._wait()
            try:
                response = self.session.get(url, params=params, timeout=(8, 35), stream=stream)
            except requests.RequestException as exc:
                last_error = exc
                continue
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "")
                try:
                    sleep_for = max(float(retry_after), 3.0)
                except ValueError:
                    sleep_for = 5.0 * (attempt + 1)
                self.next_request_at = max(self.next_request_at, time.monotonic() + min(sleep_for, 90.0))
                continue
            try:
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
        raise ValueError(f"network request failed: {last_error or 'rate limited'}")

    @staticmethod
    def _tokens(value):
        return re.findall(r"[a-z0-9]+", value.casefold())

    def _entity_for_product(self, product):
        response = self._request(
            WIKIDATA_API,
            params={"action": "wbsearchentities", "search": product.name, "language": "en", "limit": 8, "format": "json"},
        ).json()
        wanted = set(self._tokens(product.name))
        candidates = response.get("search", [])
        ranked = []
        for item in candidates:
            label = item.get("label", "")
            label_tokens = set(self._tokens(label))
            if not label_tokens:
                continue
            score = len(wanted & label_tokens) / max(1, len(wanted))
            if " ".join(self._tokens(product.name)) == " ".join(self._tokens(label)):
                score += 1
            ranked.append((score, item.get("id", "")))
        if not ranked:
            raise ValueError("no Wikidata entity search result")
        score, qid = max(ranked)
        if score < 0.55 or not re.fullmatch(r"Q\d+", qid):
            raise ValueError("no sufficiently exact Wikidata model match")
        return qid

    def _claims_for_entity(self, qid):
        data = self._request(
            WIKIDATA_API,
            params={"action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"},
        ).json()
        claims = data.get("entities", {}).get(qid, {}).get("claims", {})
        images = []
        for claim in claims.get("P18", []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(value, str):
                images.append(value)
        category = None
        for claim in claims.get("P373", []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(value, str) and value.strip():
                category = value.strip()
                break
        return images, category

    def _category_files(self, category, product_name):
        payload = self._request(
            COMMONS_API,
            params={
                "action": "query", "generator": "categorymembers", "gcmtitle": f"Category:{category}",
                "gcmtype": "file", "gcmlimit": 40, "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size",
                "iiurlwidth": 1200, "format": "json", "formatversion": 2,
            },
        ).json()
        files = []
        for page in payload.get("query", {}).get("pages", []):
            title = page.get("title", "")
            filename = title[5:] if title.casefold().startswith("file:") else title
            if model_match_score(product_name, filename) >= 0.5:
                files.append(filename)
        return files

    def _media_metadata(self, filenames):
        if not filenames:
            return []
        payload = self._request(
            COMMONS_API,
            params={
                "action": "query", "titles": "|".join(f"File:{name}" for name in filenames[:20]),
                "prop": "imageinfo|info", "iiprop": "url|extmetadata|mime|size", "iiurlwidth": 1200,
                "inprop": "url", "format": "json", "formatversion": 2,
            },
        ).json()
        records = []
        for page in payload.get("query", {}).get("pages", []):
            info = (page.get("imageinfo") or [None])[0]
            if not info or info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}:
                continue
            ext = info.get("extmetadata") or {}
            license_name = self._plain(ext.get("LicenseShortName", {}).get("value", ""))
            source_url = page.get("fullurl") or info.get("descriptionurl")
            download_url = info.get("thumburl") or info.get("url")
            if not license_name or not source_url or not download_url:
                continue
            records.append({
                "filename": normalise_file_title(page.get("title", "")), "download_url": download_url,
                "source_url": source_url, "license": license_name[:120],
                "artist": self._plain(ext.get("Artist", {}).get("value", ""))[:160],
            })
        return records

    @staticmethod
    def _plain(value):
        value = re.sub(r"<[^>]+>", " ", value or "")
        return " ".join(value.split())

    def _build_gallery(self, product):
        qid = self._entity_for_product(product)
        primary_files, commons_category = self._claims_for_entity(qid)
        filenames = list(CURATED_GALLERY_FILES.get(product.sku, ())) + list(primary_files)
        if commons_category and len(filenames) < self.max_images:
            filenames.extend(self._category_files(commons_category, product.name))
        deduped = []
        seen = set()
        for filename in filenames:
            key = normalise_file_title(filename)
            if key not in seen:
                seen.add(key)
                deduped.append(filename)
        metadata = self._media_metadata(deduped)
        if not metadata:
            raise ValueError("no licensed Commons image metadata")

        gallery = []
        source_hashes = set(ProductMedia.objects.exclude(product=product).exclude(image_sha256="").values_list("image_sha256", flat=True))
        source_phashes = set(ProductMedia.objects.exclude(product=product).exclude(perceptual_hash="").values_list("perceptual_hash", flat=True))
        for record in metadata:
            if len(gallery) >= self.max_images:
                break
            raw = self._request(record["download_url"]).content
            try:
                with Image.open(BytesIO(raw)) as opened:
                    opened.load()
                    image = ImageOps.exif_transpose(opened).convert("RGB")
                    if max(image.size) < 240 or min(image.size) < 120:
                        continue
                    if max(image.size) < 900:
                        scale = 900 / max(image.size)
                        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
                    image.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
                    digest_before = hashlib.sha256(raw).hexdigest()
                    perceptual = image_dhash(image)
                    if digest_before in source_hashes or perceptual in source_phashes:
                        continue
                    buffer = BytesIO()
                    image.save(buffer, "WEBP", quality=90, method=6)
                    gallery.append({**record, "bytes": buffer.getvalue(), "sha256": digest_before, "perceptual": perceptual})
                    source_hashes.add(digest_before)
                    source_phashes.add(perceptual)
            except (UnidentifiedImageError, OSError):
                continue
        if not gallery:
            raise ValueError("all discovered files failed local validation")
        return qid, gallery

    def _replace_gallery(self, product, prepared):
        qid, gallery = prepared
        media_root = Path(settings.MEDIA_ROOT) / "product_uploads"
        final_dir = media_root / product.sku
        staging_dir = Path(settings.MEDIA_ROOT) / ".gallery-staging" / product.sku
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        for index, item in enumerate(gallery, start=1):
            filename = "primary.webp" if index == 1 else f"gallery-{index}.webp"
            (staging_dir / filename).write_bytes(item["bytes"])

        with transaction.atomic():
            ProductMedia.objects.filter(product=product).delete()
            if final_dir.exists():
                shutil.rmtree(final_dir)
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staging_dir), str(final_dir))
            for index, item in enumerate(gallery, start=1):
                filename = "primary.webp" if index == 1 else f"gallery-{index}.webp"
                note = item["license"]
                if item.get("artist"):
                    note = f"{note} | author: {item['artist']}"
                ProductMedia.objects.create(
                    product=product, media_type="image", image_file=f"product_uploads/{product.sku}/{filename}",
                    source_url=item["source_url"], source_item_id=qid, licence_note=note[:255],
                    image_sha256=item["sha256"], perceptual_hash=item["perceptual"], is_verified=True,
                    is_primary=index == 1, display_order=index - 1,
                    alt_text_en=f"{product.name} product view {index}",
                    alt_text_ka=f"{product.name} პროდუქტის ხედვა {index}",
                    alt_text_ru=f"Вид товара {product.name} {index}",
                )
            product.is_published = product.has_verified_image
            product.save(update_fields=["is_published", "updated_at"])