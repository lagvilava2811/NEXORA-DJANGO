from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import quote_plus, urlparse

import requests
from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, transaction
from django.db.models import Count, Q

from store.catalog_sources import model_match_score
from store.models import Product, ProductMedia


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
BING_IMAGES = "https://www.bing.com/images/search"
USER_AGENT = "NEXORA-gallery-enricher/1.0 (local catalog maintenance)"
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_PAGE_BYTES = 6 * 1024 * 1024
MIN_IMAGE_BYTES = 2 * 1024
REJECTED_MEDIA_WORDS = {
    "icon", "icons", "logo", "logos", "diagram", "diagrams", "schematic",
    "blueprint", "clipart", "vector", "symbol", "wallpaper", "screenshot",
    "manual", "placeholder", "silhouette", "mockup", "mock-up", "sprite",
    "freepik", "shutterstock", "gettyimages", "dreamstime", "alamy", "stockphoto", "generated",
}
LEGACY_MARKERS = (
    "custom-generated",
    "generated high-tech vector silhouette",
    "generated placeholder",
    "legacy placeholder",
)


@dataclass(frozen=True)
class Candidate:
    download_url: str
    source_url: str
    label: str
    provider: str
    licence_note: str


@dataclass(frozen=True)
class PreparedImage:
    content: bytes
    sha256: str
    perceptual_hash: str
    width: int
    height: int


@dataclass(frozen=True)
class PreparedAsset:
    candidate: Candidate
    image: PreparedImage


@dataclass(frozen=True)
class ProductJob:
    product_id: int
    name: str
    sku: str
    existing_count: int
    existing_hashes: tuple[str, ...]


@dataclass(frozen=True)
class EnrichmentResult:
    product_id: int
    name: str
    existing_count: int
    assets: tuple[PreparedAsset, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApplyResult:
    ready: bool
    added: int
    retained: int
    legacy_removed: int


class _BingMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "a":
            return
        attributes = {str(key).casefold(): value for key, value in attrs}
        classes = set(str(attributes.get("class") or "").casefold().split())
        payload = attributes.get("m")
        if "iusc" not in classes or not payload:
            return
        try:
            record = json.loads(payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return
        if isinstance(record, dict):
            self.records.append(record)


def is_public_http_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value).strip())
    except (TypeError, ValueError):
        return False
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def extract_bing_candidates(markup: str) -> list[Candidate]:
    parser = _BingMetadataParser()
    try:
        parser.feed(markup)
    except (ValueError, TypeError):
        return []
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for record in parser.records:
        download_url = str(record.get("murl") or "").strip()
        source_url = str(record.get("purl") or "").strip()
        label = " ".join(
            str(record.get(key) or "").strip()
            for key in ("t", "desc", "alt")
            if record.get(key)
        )
        if not is_public_http_url(download_url) or not is_public_http_url(source_url):
            continue
        key = download_url.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            Candidate(
                download_url=download_url,
                source_url=source_url,
                label=label or download_url,
                provider="Bing Images",
                licence_note="Source-discovered product image; usage rights unverified",
            )
        )
    return candidates


def is_candidate_relevant(product_name: str, candidate: Candidate) -> bool:
    searchable = " ".join((candidate.label, candidate.download_url, candidate.source_url))
    normalized = re.sub(r"[^a-z0-9-]+", " ", searchable.casefold())
    words = set(normalized.split())
    if words & REJECTED_MEDIA_WORDS:
        return False
    if any(re.search(rf"\b{re.escape(word)}\b", normalized) for word in REJECTED_MEDIA_WORDS):
        return False
    return model_match_score(product_name, searchable) >= 0.60


def average_hash(image: Image.Image) -> str:
    grayscale = image.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(grayscale.getdata())
    mean = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= mean)
    return f"{value:016x}"


def hamming_distance(left: str, right: str) -> int:
    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except (TypeError, ValueError):
        return 64


def prepare_image(raw: bytes, *, min_dimension: int = 900, min_long_dimension: int = 1200) -> PreparedImage:
    if not isinstance(raw, bytes) or len(raw) < MIN_IMAGE_BYTES:
        raise ValueError("image response is empty or implausibly small")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("image exceeds the download size limit")
    try:
        with Image.open(BytesIO(raw)) as source:
            if getattr(source, "is_animated", False):
                raise ValueError("animated images are not accepted")
            source.load()
            width, height = source.size
            if width < min_dimension or height < min_dimension:
                raise ValueError(f"image is below {min_dimension}px on one axis")
            if max(width, height) < min_long_dimension:
                raise ValueError(f"image is below {min_long_dimension}px on the long axis")
            ratio = width / max(1, height)
            if ratio < 0.45 or ratio > 2.20:
                raise ValueError("image aspect ratio is not suitable for a product gallery")
            image = ImageOps.exif_transpose(source)
            if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                rgba = image.convert("RGBA")
                background = Image.new("RGBA", rgba.size, "white")
                background.alpha_composite(rgba)
                image = background.convert("RGB")
            else:
                image = image.convert("RGB")
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("download is not a valid raster image") from exc

    if ImageStat.Stat(image.convert("L").resize((128, 128))).stddev[0] < 4.0:
        raise ValueError("image has insufficient visual detail")
    image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, "WEBP", quality=90, method=6)
    content = output.getvalue()
    return PreparedImage(
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        perceptual_hash=average_hash(image),
        width=image.width,
        height=image.height,
    )


def _plain_text(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value or "").split())


def _safe_console(value) -> str:
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def _is_legacy(media: ProductMedia) -> bool:
    note = (media.licence_note or "").casefold()
    return any(marker in note for marker in LEGACY_MARKERS)


def _is_real_local(media: ProductMedia) -> bool:
    if media.media_type != "image" or not media.is_verified or not media.image_file or _is_legacy(media):
        return False
    try:
        return media.image_file.storage.exists(media.image_file.name)
    except (OSError, ValueError):
        return False


class Command(BaseCommand):
    help = (
        "Ensure every product has a local, distinct, source-tracked image gallery. "
        "Searches Wikimedia Commons first and falls back to Bing Images. Dry-run unless --apply is used."
    )

    def add_arguments(self, parser):
        parser.add_argument("--workers", type=int, default=8, help="Parallel product workers (1-32; default: 8).")
        parser.add_argument("--min-images", type=int, default=4, help="Minimum real local images per product (default: 4).")
        parser.add_argument("--limit", type=int, default=0, help="Process at most this many products; 0 means all.")
        parser.add_argument("--apply", action="store_true", help="Write downloaded media and database changes.")
        parser.add_argument(
            "--publish-ready-only",
            action="store_true",
            help="With --apply, publish only products that reach the requested image minimum; unpublish incomplete products.",
        )

    def handle(self, *args, **options):
        workers = int(options["workers"])
        min_images = int(options["min_images"])
        limit = int(options["limit"])
        apply_changes = bool(options["apply"])
        publish_ready_only = bool(options["publish_ready_only"])
        if not 1 <= workers <= 32:
            raise CommandError("--workers must be between 1 and 32")
        if not 1 <= min_images <= 12:
            raise CommandError("--min-images must be between 1 and 12")
        if limit < 0:
            raise CommandError("--limit cannot be negative")

        catalog = Product.objects.annotate(
            verified_gallery_count=Count(
                "media",
                filter=Q(media__media_type="image", media__is_verified=True) & ~Q(media__image_file=""),
                distinct=True,
            )
        )
        ready_catalog = catalog.filter(verified_gallery_count__gte=min_images)
        if apply_changes and publish_ready_only:
            ready_ids = ready_catalog.filter(is_active=True, status="active").values("pk")
            Product.objects.filter(pk__in=ready_ids).update(is_published=True)
        queryset = catalog.filter(verified_gallery_count__lt=min_images).prefetch_related("media").order_by("pk")
        products = list(queryset[:limit] if limit else queryset)
        self._thread_local = threading.local()
        self._hash_lock = threading.Lock()
        self._global_hashes = set(
            ProductMedia.objects.exclude(image_sha256__isnull=True)
            .exclude(image_sha256="")
            .values_list("image_sha256", flat=True)
        )
        jobs = [self._build_job(product) for product in products]
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(f"{mode}: {len(jobs)} product(s), minimum {min_images}, {workers} worker(s).")

        ready_count = failed_count = added_count = 0
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="gallery") as executor:
            futures = {executor.submit(self._enrich_job, job, min_images): job for job in jobs}
            for completed, future in enumerate(as_completed(futures), start=1):
                job = futures.pop(future)
                try:
                    result = future.result()
                except Exception as exc:  # a worker failure must not abort the catalog run
                    result = EnrichmentResult(job.product_id, job.name, job.existing_count, (), (_safe_console(exc),))
                if apply_changes:
                    try:
                        applied = self._apply_prepared(
                            result.product_id,
                            list(result.assets),
                            min_images=min_images,
                            publish_ready_only=publish_ready_only,
                        )
                    except Exception as exc:
                        failed_count += 1
                        self.stdout.write(self.style.WARNING(
                            _safe_console(f"[{completed}/{len(jobs)}] {result.name}: apply failed: {exc}")
                        ))
                        continue
                    ready = applied.ready
                    added = applied.added
                    detail = f"added={added}, retained={applied.retained}, legacy-removed={applied.legacy_removed}"
                else:
                    ready = result.existing_count + len(result.assets) >= min_images
                    added = len(result.assets)
                    detail = f"would-add={added}, existing={result.existing_count}"
                added_count += added
                ready_count += int(ready)
                failed_count += int(not ready)
                style = self.style.SUCCESS if ready else self.style.WARNING
                warning = f"; {' | '.join(result.warnings)}" if result.warnings and not ready else ""
                self.stdout.write(style(_safe_console(
                    f"[{completed}/{len(jobs)}] {result.name}: {'READY' if ready else 'INCOMPLETE'} ({detail}){warning}"
                )))

        self.stdout.write(self.style.SUCCESS(
            f"{mode} complete: ready={ready_count}/{len(jobs)}, added={added_count}, incomplete={failed_count}."
        ))

    def _build_job(self, product: Product) -> ProductJob:
        real_media = [media for media in product.media.all() if _is_real_local(media)]
        hashes: list[str] = []
        for media in real_media:
            try:
                with media.image_file.open("rb") as handle:
                    with Image.open(handle) as image:
                        image.load()
                        hashes.append(average_hash(ImageOps.exif_transpose(image)))
            except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
                if media.perceptual_hash:
                    hashes.append(media.perceptual_hash)
        return ProductJob(product.pk, product.name, product.sku, len(real_media), tuple(hashes))

    def _session(self):
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.8",
            })
            self._thread_local.session = session
        return session

    def _request_bytes(self, url, *, params=None, max_bytes, image=False):
        if not is_public_http_url(url):
            raise ValueError("refusing a non-public URL")
        last_error = None
        for attempt in range(3):
            response = None
            try:
                response = self._session().get(
                    url,
                    params=params,
                    timeout=(8, 30),
                    stream=True,
                    allow_redirects=True,
                    headers={"Accept": "image/avif,image/webp,image/png,image/jpeg,image/*"} if image else None,
                )
                if not is_public_http_url(response.url):
                    raise ValueError("remote request redirected to a non-public URL")
                if response.status_code == 429 or response.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {response.status_code}")
                response.raise_for_status()
                content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].casefold()
                if image and content_type and not (
                    content_type.startswith("image/") or content_type == "application/octet-stream"
                ):
                    raise ValueError(f"unexpected image content type: {content_type}")
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > max_bytes:
                    raise ValueError("remote response exceeds size limit")
                chunks = []
                total = 0
                for chunk in response.iter_content(64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("remote response exceeds size limit")
                    chunks.append(chunk)
                return b"".join(chunks)
            except (requests.RequestException, ValueError, OSError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(min(4.0, 1.0 * (2 ** attempt)))
            finally:
                if response is not None:
                    response.close()
        raise ValueError(f"remote request failed: {_safe_console(last_error or 'unknown error')}")

    def _request_json(self, url, *, params=None):
        payload = self._request_bytes(url, params=params, max_bytes=MAX_PAGE_BYTES)
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("remote API returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("remote API returned an unexpected document")
        return value

    def _search_commons(self, product_name: str) -> list[Candidate]:
        payload = self._request_json(
            COMMONS_API,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f'"{product_name}"',
                "gsrnamespace": 6,
                "gsrlimit": 40,
                "prop": "imageinfo|info",
                "iiprop": "url|mime|size|extmetadata",
                "iiurlwidth": 1600,
                "inprop": "url",
                "format": "json",
                "formatversion": 2,
            },
        )
        candidates: list[Candidate] = []
        for page in payload.get("query", {}).get("pages", []):
            if not isinstance(page, dict):
                continue
            info = (page.get("imageinfo") or [None])[0]
            if not isinstance(info, dict):
                continue
            if info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}:
                continue
            title = str(page.get("title") or "")
            label = title[5:] if title.casefold().startswith("file:") else title
            download_url = str(info.get("thumburl") or info.get("url") or "")
            source_url = str(page.get("fullurl") or info.get("descriptionurl") or "")
            metadata = info.get("extmetadata") or {}
            licence = _plain_text(str((metadata.get("LicenseShortName") or {}).get("value") or ""))
            author = _plain_text(str((metadata.get("Artist") or {}).get("value") or ""))
            note = licence or "Wikimedia Commons source metadata"
            if author:
                note = f"{note} | author: {author}"
            candidate = Candidate(download_url, source_url, label, "Wikimedia Commons", note[:255])
            if is_public_http_url(download_url) and is_public_http_url(source_url) and is_candidate_relevant(product_name, candidate):
                candidates.append(candidate)
        return self._dedupe_candidates(candidates)

    def _search_bing(self, product_name: str) -> list[Candidate]:
        candidates = []
        searches = (
            f'"{product_name}" product front back side',
            f'"{product_name}" official product images',
            f'"{product_name}" front view rear view',
        )
        for search in searches:
            query = quote_plus(search)
            try:
                markup = self._request_bytes(
                    f"{BING_IMAGES}?q={query}&form=HDRSC2&first=1",
                    max_bytes=MAX_PAGE_BYTES,
                ).decode("utf-8", "replace")
            except (requests.RequestException, ValueError):
                continue
            candidates.extend(
                candidate for candidate in extract_bing_candidates(markup)
                if is_candidate_relevant(product_name, candidate)
            )
        return self._dedupe_candidates(candidates)

    @staticmethod
    def _dedupe_candidates(candidates):
        output = []
        seen = set()
        for candidate in candidates:
            key = candidate.download_url.casefold()
            if key not in seen:
                seen.add(key)
                output.append(candidate)
        return output

    def _enrich_job(self, job: ProductJob, min_images: int) -> EnrichmentResult:
        close_old_connections()
        needed = max(0, min_images - job.existing_count)
        if needed == 0:
            return EnrichmentResult(job.product_id, job.name, job.existing_count, ())
        assets: list[PreparedAsset] = []
        local_hashes = list(job.existing_hashes)
        warnings: list[str] = []
        try:
            sources = self._search_commons(job.name)
        except Exception as exc:
            sources = []
            warnings.append(f"Commons: {_safe_console(exc)}")
        assets.extend(self._prepare_candidates(job.name, sources, needed, local_hashes))
        if len(assets) < needed:
            try:
                sources = self._search_bing(job.name)
            except Exception as exc:
                sources = []
                warnings.append(f"Bing: {_safe_console(exc)}")
            assets.extend(self._prepare_candidates(job.name, sources, needed - len(assets), local_hashes))
        close_old_connections()
        return EnrichmentResult(job.product_id, job.name, job.existing_count, tuple(assets), tuple(warnings))

    def _prepare_candidates(self, product_name, candidates, needed, local_hashes):
        output: list[PreparedAsset] = []
        for candidate in candidates:
            if len(output) >= needed:
                break
            try:
                prepared = prepare_image(
                    self._request_bytes(candidate.download_url, max_bytes=MAX_IMAGE_BYTES, image=True)
                )
            except (OSError, ValueError, requests.RequestException):
                continue
            if any(hamming_distance(prepared.perceptual_hash, known) <= 6 for known in local_hashes):
                continue
            with self._hash_lock:
                if prepared.sha256 in self._global_hashes:
                    continue
                self._global_hashes.add(prepared.sha256)
            local_hashes.append(prepared.perceptual_hash)
            output.append(PreparedAsset(candidate, prepared))
        return output

    def _apply_prepared(self, product_id, assets, *, min_images, publish_ready_only):
        created_names: list[tuple[object, str]] = []
        legacy_names: list[tuple[object, str]] = []
        try:
            with transaction.atomic():
                product = Product.objects.select_for_update().get(pk=product_id)
                all_media = list(product.media.all())
                real_media = [media for media in all_media if _is_real_local(media)]
                legacy = [media for media in all_media if _is_legacy(media)]
                needed = max(0, min_images - len(real_media))
                next_order = max((media.display_order for media in all_media), default=-1) + 1
                created: list[ProductMedia] = []
                for index, asset in enumerate(assets[:needed], start=1):
                    if ProductMedia.objects.filter(image_sha256=asset.image.sha256).exists():
                        continue
                    media = ProductMedia(
                        product=product,
                        media_type="image",
                        source_url=asset.candidate.source_url[:200],
                        source_item_id=asset.candidate.provider[:32],
                        image_sha256=asset.image.sha256,
                        perceptual_hash=asset.image.perceptual_hash,
                        licence_note=asset.candidate.licence_note[:255],
                        is_verified=True,
                        is_primary=False,
                        display_order=next_order + index - 1,
                        alt_text_en=f"{product.name} product view {len(real_media) + index}",
                        alt_text_ka=f"{product.name} პროდუქტის ხედი {len(real_media) + index}",
                        alt_text_ru=f"{product.name}: вид товара {len(real_media) + index}",
                    )
                    safe_sku = re.sub(r"[^A-Za-z0-9._-]+", "-", product.sku).strip(".-") or f"product-{product.pk}"
                    filename = f"{safe_sku}/gallery-auto-{asset.image.sha256[:16]}.webp"
                    media.image_file.save(filename, ContentFile(asset.image.content), save=False)
                    created_names.append((media.image_file.storage, media.image_file.name))
                    media.save()
                    created.append(media)
                real_media.extend(created)
                ready = len(real_media) >= min_images
                removed = 0
                if ready:
                    for media in legacy:
                        if media.image_file:
                            legacy_names.append((media.image_file.storage, media.image_file.name))
                    removed = len(legacy)
                    if legacy:
                        ProductMedia.objects.filter(pk__in=[media.pk for media in legacy]).delete()
                    primary = next((media for media in real_media if media.is_primary), None)
                    if primary is None and real_media:
                        primary = sorted(real_media, key=lambda item: (item.display_order, item.pk or 0))[0]
                    if primary is not None:
                        ProductMedia.objects.filter(
                            product=product, media_type="image", is_primary=True
                        ).exclude(pk=primary.pk).update(is_primary=False)
                        if not primary.is_primary:
                            ProductMedia.objects.filter(pk=primary.pk).update(is_primary=True)
                if publish_ready_only:
                    should_publish = ready and product.is_active and product.status == "active"
                    if product.is_published != should_publish:
                        product.is_published = should_publish
                        product.save(update_fields=["is_published", "updated_at"])
                if legacy_names:
                    transaction.on_commit(lambda: self._delete_files(tuple(legacy_names)))
                return ApplyResult(ready, len(created), len(real_media) - len(created), removed)
        except Exception:
            self._delete_files(tuple(created_names))
            raise

    @staticmethod
    def _delete_files(files):
        for storage, name in files:
            try:
                if name and storage.exists(name):
                    storage.delete(name)
            except (OSError, ValueError):
                continue
