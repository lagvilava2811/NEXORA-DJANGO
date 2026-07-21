from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from store.catalog_sources import (
    CATEGORY_SOURCES,
    SOURCE_BY_SLUG,
    build_sparql,
    commons_filename,
    deterministic_int,
    deterministic_price,
    entity_id,
    image_dhash,
    model_media_matches,
    normalise_file_title,
    round_robin,
    safe_brand,
    variant_blueprints,
)
from store.models import Brand, Category, OrderItem, Product, ProductMedia, ProductVariant

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
COMMONS_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "NexoraCatalog/3.0 (source-tracked local commerce catalogue)"
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/tiff"}


class Command(BaseCommand):
    help = "Build and import 1,000+ exact Wikidata product models with unique local Wikimedia images."

    def add_arguments(self, parser):
        parser.add_argument("--target", type=int, default=1000)
        parser.add_argument("--workers", type=int, default=6)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--metadata-only", action="store_true")
        parser.add_argument("--replace", action="store_true")
        parser.add_argument("--refresh-manifest", action="store_true")
        parser.add_argument("--prune-unreferenced", action="store_true")
        parser.add_argument(
            "--manifest",
            default="store/data/wikidata_catalog_manifest.json",
            help="Cached, source-tracked Wikidata/Wikimedia manifest.",
        )

    def handle(self, *args, **options):
        target = max(1000, options["target"])
        workers = max(1, min(options["workers"], 32))
        manifest_path = Path(options["manifest"])
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        staging_root = Path(settings.MEDIA_ROOT) / ".wikidata-staging"
        staging_root.mkdir(parents=True, exist_ok=True)

        self.http = self._session(pool_size=workers * 3, retry_total=7)
        self.download_http = self._session(pool_size=workers * 3, retry_total=0, status_forcelist=(500, 502, 503, 504))
        self.download_lock = threading.Lock()
        self.download_next_at = 0.0
        self.download_interval = 0.55
        self.download_stats = Counter()
        self.download_progress_path = staging_root / "download_progress.json"
        candidates = self._load_or_build_manifest(
            manifest_path,
            refresh=options["refresh_manifest"],
        )
        if len(candidates) < target:
            raise CommandError(
                f"Only {len(candidates)} licensed raster candidates are available; {target} required."
            )

        groups = defaultdict(list)
        for candidate in candidates:
            groups[candidate["category"]].append(candidate)
        ordered = round_robin(groups)
        if options["metadata_only"]:
            prepared = []
            for item in ordered[:target]:
                record = dict(item)
                record["width"] = int(item.get("source_width") or 0)
                record["height"] = int(item.get("source_height") or 0)
                prepared.append(record)
            counts = Counter(item["category"] for item in prepared)
            self.stdout.write(f"Prepared {len(prepared)} metadata-only product records.")
            self.stdout.write("Category distribution: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
            if not options["apply"]:
                self.stdout.write(self.style.SUCCESS("Metadata-only dry run complete; no database changes made."))
                return
            self._apply_catalog(prepared, replace=options["replace"], include_media=False)
            self.stdout.write(self.style.SUCCESS(f"Imported {len(prepared)} unpublished metadata records; galleries remain quality-gated."))
            return

        prepared, failures = self._stage_catalog(ordered, staging_root, target, workers)
        counts = Counter(item["category"] for item in prepared)
        self.stdout.write(self.style.SUCCESS(f"Prepared {len(prepared)} exact, unique, local product images."))
        self.stdout.write("Category distribution: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
        if failures:
            self.stdout.write(self.style.WARNING(f"Skipped {len(failures)} candidates during image validation."))
            for failure in failures[:20]:
                self.stdout.write(self.style.WARNING(f"  {failure}"))

        if len(prepared) < target:
            raise CommandError(f"Integrity gate failed: {len(prepared)} valid unique products; {target} required.")

        prepared = prepared[:target]
        prepared_path = staging_root / "prepared_manifest.json"
        prepared_path.write_text(json.dumps(prepared, ensure_ascii=False, indent=2), encoding="utf-8")

        if not options["apply"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete. Staged media retained for a resumable --apply run."))
            return

        self._apply_catalog(prepared, replace=options["replace"])
        audit = self._audit_import(target)
        self.stdout.write(self.style.SUCCESS(f"Catalogue integrity audit passed: {json.dumps(audit, sort_keys=True)}"))
        if options["prune_unreferenced"]:
            removed = self._prune_unreferenced_media()
            self.stdout.write(self.style.SUCCESS(f"Removed {removed} unreferenced legacy media files/directories."))

    @staticmethod
    def _session(pool_size=12, retry_total=5, status_forcelist=(429, 500, 502, 503, 504)):
        retry = Retry(
            total=retry_total,
            connect=retry_total,
            read=retry_total,
            status=retry_total,
            backoff_factor=0.75,
            status_forcelist=status_forcelist,
            allowed_methods=frozenset(("GET", "POST")),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=pool_size, pool_maxsize=pool_size)
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        session.mount("https://", adapter)
        return session

    def _load_or_build_manifest(self, path: Path, refresh: bool):
        if path.exists() and not refresh:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                exact = [
                    item for item in data
                    if model_media_matches(item.get("name", ""), item.get("commons_filename", ""))
                ]
                self.stdout.write(
                    f"Loaded {len(exact)}/{len(data)} cached records that pass exact-model media matching from {path}."
                )
                return exact

        grouped = {}
        seen_items = set()
        seen_files = set()
        for index, source in enumerate(CATEGORY_SOURCES, start=1):
            self.stdout.write(f"[{index}/{len(CATEGORY_SOURCES)}] Querying {source.name_en} exact model items…")
            response = self.http.get(
                WIKIDATA_ENDPOINT,
                params={"query": build_sparql(source), "format": "json"},
                timeout=150,
            )
            response.raise_for_status()
            bindings = response.json().get("results", {}).get("bindings", [])
            records = []
            for binding in bindings:
                try:
                    qid = entity_id(binding["item"]["value"])
                    filename = commons_filename(binding["image"]["value"])
                except (KeyError, ValueError):
                    continue
                file_key = normalise_file_title(filename)
                if qid in seen_items or file_key in seen_files:
                    continue
                name = self._value(binding, "itemLabel").strip()
                if not name or re.fullmatch(r"Q\d+", name):
                    continue
                if not model_media_matches(name, filename):
                    continue
                seen_items.add(qid)
                seen_files.add(file_key)
                records.append(
                    {
                        "qid": qid,
                        "name": name[:150],
                        "category": source.slug,
                        "manufacturer": self._value(binding, "manufacturer"),
                        "description": self._value(binding, "description"),
                        "website": self._value(binding, "website"),
                        "released": self._value(binding, "released"),
                        "entity_url": binding["item"]["value"].replace("http://", "https://"),
                        "commons_filename": filename,
                    }
                )
            grouped[source.slug] = records
            self.stdout.write(f"  found {len(records)} unique exact items")
            time.sleep(1.25)

        candidates = round_robin(grouped)
        self.stdout.write(f"Resolving Commons licence and thumbnail metadata for {len(candidates)} files…")
        metadata = self._commons_metadata([item["commons_filename"] for item in candidates])
        enriched = []
        for candidate in candidates:
            info = metadata.get(normalise_file_title(candidate["commons_filename"]))
            if not info or info.get("mime") not in ALLOWED_MIME:
                continue
            if not info.get("source_url") or not info.get("license") or not info.get("download_url"):
                continue
            candidate.update(info)
            enriched.append(candidate)

        path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Saved {len(enriched)} licensed raster source records to {path}."))
        return enriched

    @staticmethod
    def _value(binding, key):
        return binding.get(key, {}).get("value", "")

    def _commons_metadata(self, filenames):
        output = {}
        for offset in range(0, len(filenames), 40):
            batch = filenames[offset : offset + 40]
            response = self.http.post(
                COMMONS_ENDPOINT,
                data={
                    "action": "query",
                    "titles": "|".join(f"File:{name}" for name in batch),
                    "prop": "imageinfo|info",
                    "iiprop": "url|extmetadata|mime|size",
                    "iiurlwidth": 1200,
                    "inprop": "url",
                    "redirects": 1,
                    "format": "json",
                    "formatversion": 2,
                    "maxlag": 5,
                },
                timeout=120,
            )
            response.raise_for_status()
            for page in response.json().get("query", {}).get("pages", []):
                imageinfo = (page.get("imageinfo") or [None])[0]
                if not imageinfo:
                    continue
                ext = imageinfo.get("extmetadata") or {}
                licence = self._clean_meta(ext, "LicenseShortName") or self._clean_meta(ext, "UsageTerms")
                license_url = self._clean_meta(ext, "LicenseUrl")
                artist = self._clean_meta(ext, "Artist")
                source_url = page.get("fullurl") or imageinfo.get("descriptionurl")
                title_key = normalise_file_title(page.get("title", ""))
                output[title_key] = {
                    "download_url": imageinfo.get("thumburl") or imageinfo.get("url"),
                    "original_url": imageinfo.get("url"),
                    "source_url": source_url,
                    "license": licence[:120],
                    "license_url": license_url[:300],
                    "artist": artist[:200],
                    "mime": imageinfo.get("mime", ""),
                    "source_width": imageinfo.get("width"),
                    "source_height": imageinfo.get("height"),
                }
            self.stdout.write(f"  metadata {min(offset + 40, len(filenames))}/{len(filenames)}")
            time.sleep(0.35)
        return output

    @staticmethod
    def _clean_meta(extmetadata, key):
        value = html.unescape((extmetadata.get(key) or {}).get("value", ""))
        value = re.sub(r"<[^>]+>", " ", value)
        return " ".join(value.split())

    def _stage_catalog(self, candidates, staging_root, target, workers):
        prepared = []
        failures = []
        seen_sha = set()
        seen_perceptual = set()
        lock = threading.Lock()
        chunk_size = max(32, workers * 8)

        for offset in range(0, len(candidates), chunk_size):
            if len(prepared) >= target:
                break
            chunk = candidates[offset : offset + chunk_size]
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(self._stage_one, candidate, staging_root): candidate for candidate in chunk}
                for future in as_completed(futures):
                    candidate = futures[future]
                    try:
                        item = future.result()
                    except Exception as exc:
                        failures.append(f"{candidate['qid']} {candidate['name']}: {exc}")
                        continue
                    with lock:
                        if item["image_sha256"] in seen_sha:
                            failures.append(f"{item['qid']} {item['name']}: duplicate SHA-256")
                            continue
                        if item["perceptual_hash"] in seen_perceptual:
                            failures.append(f"{item['qid']} {item['name']}: duplicate perceptual hash")
                            continue
                        seen_sha.add(item["image_sha256"])
                        seen_perceptual.add(item["perceptual_hash"])
                        prepared.append(item)
            self.stdout.write(f"  validated {len(prepared)}/{target} unique local images")
        return prepared, failures

    def _stage_one(self, candidate, staging_root):
        folder = staging_root / candidate["qid"]
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / "primary.webp"
        source_json = folder / "source.json"

        if output.exists() and source_json.exists():
            with Image.open(output) as image:
                image.load()
                width, height = image.size
                perceptual = image_dhash(image)
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
        else:
            raw = self._download_bytes(candidate["download_url"])
            if not raw or len(raw) > MAX_DOWNLOAD_BYTES:
                raise ValueError(f"invalid download size {len(raw)}")
            try:
                with Image.open(BytesIO(raw)) as source:
                    source.load()
                    source = ImageOps.exif_transpose(source)
                    width, height = source.size
                    if max(width, height) < 240 or min(width, height) < 120:
                        raise ValueError(f"image too small: {width}x{height}")
                    image = self._to_rgb(source)
                    image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                    perceptual = image_dhash(image)
                    temp = folder / "primary.tmp.webp"
                    image.save(temp, "WEBP", quality=86, method=6)
                    temp.replace(output)
                    width, height = image.size
            except (UnidentifiedImageError, OSError) as exc:
                raise ValueError(f"invalid raster image: {exc}") from exc
            digest = hashlib.sha256(output.read_bytes()).hexdigest()
            source_json.write_text(
                json.dumps(
                    {
                        "wikidata_item": candidate["qid"],
                        "wikidata_url": candidate["entity_url"],
                        "commons_file": candidate["commons_filename"],
                        "commons_page": candidate["source_url"],
                        "download_url": candidate["download_url"],
                        "original_url": candidate.get("original_url", ""),
                        "license": candidate["license"],
                        "license_url": candidate.get("license_url", ""),
                        "artist": candidate.get("artist", ""),
                        "sha256": digest,
                        "perceptual_hash": perceptual,
                        "downloaded_at": datetime.now(timezone.utc).isoformat(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

        item = dict(candidate)
        item.update(
            {
                "staged_image": str(output),
                "staged_source": str(source_json),
                "image_sha256": digest,
                "perceptual_hash": perceptual,
                "width": width,
                "height": height,
            }
        )
        return item

    def _record_download(self, outcome):
        with self.download_lock:
            self.download_stats[outcome] += 1
            total = sum(self.download_stats.values())
            if total % 10 == 0:
                self.download_progress_path.write_text(
                    json.dumps({"total": total, **self.download_stats}, sort_keys=True),
                    encoding="utf-8",
                )

    def _download_bytes(self, url):
        last_error = None
        for attempt in range(3):
            with self.download_lock:
                now = time.monotonic()
                wait_for = max(0.0, self.download_next_at - now)
                if wait_for:
                    time.sleep(wait_for)
                self.download_next_at = time.monotonic() + self.download_interval
            try:
                response = self.download_http.get(url, timeout=(5, 15))
            except requests.RequestException as exc:
                last_error = exc
                self._record_download("network_error")
                continue
            if response.status_code == 429:
                self._record_download("rate_limited")
                retry_after = response.headers.get("Retry-After", "")
                try:
                    pause = max(3.0, min(float(retry_after), 20.0))
                except (TypeError, ValueError):
                    pause = min(3.0 * (attempt + 1), 12.0)
                with self.download_lock:
                    self.download_next_at = max(self.download_next_at, time.monotonic() + pause)
                continue
            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                last_error = exc
                self._record_download("http_error")
                continue
            self._record_download("ok")
            return response.content
        if last_error:
            raise ValueError(f"Wikimedia download failed after bounded retries: {last_error}") from last_error
        raise ValueError("Wikimedia rate limit persisted after bounded retries")

    @staticmethod
    def _to_rgb(image):
        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            canvas = Image.new("RGBA", rgba.size, "white")
            canvas.alpha_composite(rgba)
            return canvas.convert("RGB")
        return image.convert("RGB")

    def _apply_catalog(self, prepared, replace, include_media=True):
        if include_media:
            media_root = Path(settings.MEDIA_ROOT) / "product_uploads"
            media_root.mkdir(parents=True, exist_ok=True)
            copied = {}
            for item in prepared:
                sku = f"WD-{item['qid']}"
                destination = media_root / sku
                destination.mkdir(parents=True, exist_ok=True)
                image_target = destination / "primary.webp"
                source_target = destination / "source.json"
                shutil.copy2(item["staged_image"], image_target)
                shutil.copy2(item["staged_source"], source_target)
                copied[item["qid"]] = image_target
    
        protected_ids = set(OrderItem.objects.values_list("product_id", flat=True))
        with transaction.atomic():
            if replace:
                Product.objects.filter(pk__in=protected_ids).update(is_published=False, is_active=False, status="archived")
                Product.objects.exclude(pk__in=protected_ids).delete()

            category_objects = {}
            for position, source in enumerate(CATEGORY_SOURCES):
                category, _ = Category.objects.update_or_create(
                    slug=source.slug,
                    defaults={
                        "name": source.name_en,
                        "name_en": source.name_en,
                        "name_ka": source.name_ka,
                        "name_ru": source.name_ru,
                        "display_order": position,
                        "is_active": True,
                        "description": f"Verified real {source.name_en.lower()} with locally stored source-tracked media.",
                        "seo_title": f"{source.name_en} | NEXORA",
                        "seo_description": f"Shop verified {source.name_en.lower()} with local product images and transparent provenance.",
                    },
                )
                category_objects[source.slug] = category

            for index, item in enumerate(prepared, start=1):
                source = SOURCE_BY_SLUG[item["category"]]
                category = category_objects[item["category"]]
                if not include_media:
                    duplicate = Product.objects.filter(name__iexact=item["name"], category=category).exclude(external_id=item["qid"]).first()
                    if duplicate is not None:
                        continue
                brand_name = safe_brand(item["name"], item.get("manufacturer"))
                # This is a stable, non-security fallback identifier.  Keeping
                # SHA-1 preserves existing import slugs while making its intent
                # explicit to security tooling.
                brand_slug = slugify(brand_name)[:70] or f"brand-{hashlib.sha1(brand_name.encode(), usedforsecurity=False).hexdigest()[:8]}"
                brand, _ = Brand.objects.get_or_create(
                    slug=brand_slug,
                    defaults={"name": brand_name, "is_featured": index <= 24},
                )
                year = self._release_year(item.get("released"))
                price = deterministic_price(item["qid"], source)
                stock = deterministic_int(f"stock:{item['qid']}", 6, 48)
                rating = Decimal("0.0")
                description_en = item.get("description") or f"A verified {source.name_en.lower()} model by {brand_name}."
                release_text = str(year) if year else "catalogued model"
                short_en = f"{brand_name} · {source.name_en} · {release_text}"
                short_ka = f"{brand_name} · {source.name_ka} · {release_text}"
                short_ru = f"{brand_name} · {source.name_ru} · {release_text}"
                full_ka = f"{item['name']} — რეალური {source.name_ka.lower()} მოდელი. მწარმოებელი: {brand_name}. წყარო და ფოტო დადასტურებულია Wikidata/Wikimedia-ით."
                full_ru = f"{item['name']} — реальная модель категории «{source.name_ru}». Производитель: {brand_name}. Источник и изображение подтверждены Wikidata/Wikimedia."
                specs = {
                    "manufacturer": brand_name,
                    "category": source.name_en,
                    "release_year": year or "—",
                    "wikidata_id": item["qid"],
                    "image_resolution": f"{item['width']}×{item['height']}",
                    "media_license": item["license"],
                }
                product, _ = Product.objects.update_or_create(
                    external_id=item["qid"],
                    defaults={
                        "brand_obj": brand,
                        "brand": brand_name,
                        "primary_category": category,
                        "category": category,
                        "name": item["name"],
                        "name_en": item["name"],
                        "name_ka": item["name"],
                        "name_ru": item["name"],
                        "slug": f"{slugify(item['name'])[:120]}-{item['qid'].lower()}",
                        "sku": f"WD-{item['qid']}",
                        "short_description": short_en,
                        "short_description_en": short_en,
                        "short_description_ka": short_ka,
                        "short_description_ru": short_ru,
                        "description": description_en,
                        "full_description": description_en,
                        "full_description_en": description_en,
                        "full_description_ka": full_ka,
                        "full_description_ru": full_ru,
                        "warranty_months": 24,
                        "specs": specs,
                        "price": price,
                        "compare_at_price": (price * Decimal("1.10")).quantize(Decimal("1.00")),
                        "status": "active",
                        "is_featured": index <= 24,
                        "is_new": bool(year and year >= 2024),
                        "is_best_seller": index <= 60,
                        "is_refurbished": bool(year and year < 2020),
                        "is_published": False,
                        'rating_average': Decimal('0.0'),
                        'rating': Decimal('0.0'),
                        'rating_count': 0,
                        "review_count": 0,
                        "image": "",
                        "source_url": item.get("website") or item["entity_url"],
                        "image_licence": item["license"],
                        "stock": stock,
                        "seo_title": f"{item['name']} | NEXORA",
                        "seo_description": description_en[:300],
                        "is_active": True,
                    },
                )
                product.categories.set([category])
                if include_media:
                    product.media.all().delete()
                    relative_image = f"product_uploads/WD-{item['qid']}/primary.webp"
                    ProductMedia.objects.create(
                        product=product,
                        media_type="image",
                        image_file=relative_image,
                        external_url=item.get("original_url") or item["download_url"],
                        source_url=item["source_url"],
                        source_item_id=item["qid"],
                        licence_note=self._licence_note(item),
                        image_sha256=item["image_sha256"],
                        perceptual_hash=item["perceptual_hash"],
                        is_verified=True,
                        is_primary=True,
                        alt_text_en=f"{item['name']} product image",
                        alt_text_ka=f"{item['name']} პროდუქტის ფოტო",
                        alt_text_ru=f"Изображение товара {item['name']}",
                    )
                product.variants.all().delete()
                for variant_index, blueprint in enumerate(variant_blueprints(item["category"]), start=1):
                    ProductVariant.objects.create(
                        product=product,
                        name=blueprint["name"],
                        sku=f"WD-{item['qid']}-{variant_index}",
                        storage=blueprint.get("storage", ""),
                        ram=blueprint.get("ram", ""),
                        size=blueprint.get("size", ""),
                        price_delta=blueprint["price_delta"],
                        stock_quantity=max(1, stock // len(variant_blueprints(item["category"]))),
                        stock=max(1, stock // len(variant_blueprints(item["category"]))),
                        is_active=True,
                    )
                if include_media:
                    product.is_published = product.has_verified_image
                    product.save(update_fields=["is_published", "updated_at"])

    @staticmethod
    def _release_year(value):
        match = re.match(r"(\d{4})", value or "")
        return int(match.group(1)) if match else None

    @staticmethod
    def _licence_note(item):
        parts = [item.get("license", "Wikimedia Commons")]
        if item.get("artist"):
            parts.append(f"author: {item['artist']}")
        if item.get("license_url"):
            parts.append(item["license_url"])
        return " | ".join(parts)[:255]

    def _audit_import(self, target):
        products = Product.objects.published().filter(external_id__isnull=False)
        media = ProductMedia.objects.filter(
            product__in=products,
            is_primary=True,
            is_verified=True,
            image_file__isnull=False,
        ).exclude(image_file="")
        product_count = products.count()
        media_count = media.count()
        hashes = list(media.values_list("image_sha256", flat=True))
        perceptual = list(media.values_list("perceptual_hash", flat=True))
        files = [Path(settings.MEDIA_ROOT) / value for value in media.values_list("image_file", flat=True)]
        existing = sum(path.is_file() for path in files)
        if product_count < target:
            raise CommandError(f"Post-import product audit failed: {product_count} < {target}")
        if media_count != product_count or existing != product_count:
            raise CommandError(
                f"Post-import media audit failed: products={product_count}, media={media_count}, files={existing}"
            )
        if len(set(hashes)) != product_count or len(set(perceptual)) != product_count:
            raise CommandError("Post-import uniqueness audit failed")
        return {
            "published_products": product_count,
            "verified_media": media_count,
            "existing_local_files": existing,
            "unique_sha256": len(set(hashes)),
            "unique_perceptual_hash": len(set(perceptual)),
            "variants": ProductVariant.objects.filter(product__in=products).count(),
        }

    def _prune_unreferenced_media(self):
        root = (Path(settings.MEDIA_ROOT) / "product_uploads").resolve()
        if not root.is_dir() or root == Path(settings.MEDIA_ROOT).resolve():
            raise CommandError("Unsafe product media root; refusing to prune")
        referenced = set()
        for value in ProductMedia.objects.exclude(image_file="").values_list("image_file", flat=True):
            referenced.add((Path(settings.MEDIA_ROOT) / value).resolve())
        keep_dirs = {path.parent for path in referenced}
        removed = 0
        for child in list(root.iterdir()):
            resolved = child.resolve()
            if resolved.parent != root:
                raise CommandError(f"Unsafe media path encountered: {resolved}")
            if child.is_dir() and resolved not in keep_dirs:
                shutil.rmtree(child)
                removed += 1
            elif child.is_file() and resolved not in referenced:
                child.unlink()
                removed += 1
        return removed
