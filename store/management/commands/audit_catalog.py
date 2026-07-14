from collections import Counter, defaultdict
from itertools import combinations

from PIL import Image
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Prefetch, Q

from store.models import Product, ProductMedia, ProductSpecificationValue


class Command(BaseCommand):
    help = "Audit the published catalog for product, media, localization, and review integrity."

    MAX_EXAMPLES_PER_RULE = 8

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit non-zero when any audit requirement fails.",
        )
        parser.add_argument(
            "--minimum-products",
            type=int,
            default=1000,
            help="Required published product count (default: 1000).",
        )
        parser.add_argument(
            "--minimum-images",
            type=int,
            default=4,
            help="Required verified local images per published product (default: 4).",
        )

    def handle(self, *args, **options):
        minimum_products = options["minimum_products"]
        minimum_images = options["minimum_images"]
        if minimum_products < 0 or minimum_images < 0:
            raise CommandError("Minimum values cannot be negative.")

        issues = Counter()
        examples = defaultdict(list)

        def record(rule, subject, message):
            issues[rule] += 1
            if len(examples[rule]) < self.MAX_EXAMPLES_PER_RULE:
                examples[rule].append(f"{subject}: {message}")

        verified_media = ProductMedia.objects.filter(
            media_type="image",
            is_verified=True,
        ).order_by("product_id", "-is_primary", "display_order", "pk")
        specification_values = ProductSpecificationValue.objects.exclude(value="")
        products = list(
            Product.objects.filter(
                is_active=True,
                is_published=True,
                status="active",
            )
            .select_related("category", "primary_category")
            .prefetch_related(
                Prefetch("media", queryset=verified_media, to_attr="audit_verified_images"),
                Prefetch(
                    "specification_values",
                    queryset=specification_values,
                    to_attr="audit_specification_values",
                ),
            )
            .annotate(
                approved_review_count=Count(
                    "reviews",
                    filter=Q(reviews__is_approved=True),
                    distinct=True,
                )
            )
            .order_by("pk")
        )

        published_count = len(products)
        if published_count < minimum_products:
            record(
                "minimum_products",
                "catalog",
                f"{published_count} published; requires at least {minimum_products}",
            )

        category_distribution = Counter()
        sha_media = defaultdict(list)
        verified_image_total = 0
        local_image_total = 0

        for product in products:
            subject = f"{product.sku} ({product.slug})"
            category = product.primary_category or product.category
            category_distribution[category.slug if category else "uncategorized"] += 1

            self._audit_localization(product, subject, record)
            self._audit_specs(product, subject, record)

            if product.review_count != product.approved_review_count:
                record(
                    "review_count",
                    subject,
                    f"stored={product.review_count}, approved={product.approved_review_count}",
                )

            media_items = product.audit_verified_images
            verified_image_total += len(media_items)
            existing_local = []
            hashes = []

            for media in media_items:
                media_subject = f"{subject} media#{media.pk}"
                exists = self._file_exists(media)
                if not media.image_file:
                    record("missing_file", media_subject, "image_file is empty")
                elif not exists:
                    record(
                        "missing_file",
                        media_subject,
                        f"local file does not exist: {media.image_file.name}",
                    )
                else:
                    existing_local.append(media)
                    local_image_total += 1
                    self._audit_dimensions(media, media_subject, record)

                digest = (media.image_sha256 or "").strip().lower()
                if not digest:
                    record("missing_sha256", media_subject, "image_sha256 is empty")
                elif not self._is_hex(digest, 64):
                    record("invalid_sha256", media_subject, "image_sha256 must be 64 hexadecimal characters")
                else:
                    sha_media[digest].append(media_subject)

                perceptual_hash = (media.perceptual_hash or "").strip().lower()
                if not perceptual_hash:
                    record("missing_perceptual_hash", media_subject, "perceptual_hash is empty")
                elif not self._is_hex(perceptual_hash, 16):
                    record(
                        "invalid_perceptual_hash",
                        media_subject,
                        "perceptual_hash must be 16 hexadecimal characters",
                    )
                else:
                    hashes.append((media, perceptual_hash))

                for language in ("ka", "en", "ru"):
                    if not (getattr(media, f"alt_text_{language}", "") or "").strip():
                        record(
                            "missing_alt_text",
                            media_subject,
                            f"alt_text_{language} is empty",
                        )

            if len(existing_local) < minimum_images:
                record(
                    "minimum_images",
                    subject,
                    f"{len(existing_local)} verified local images; requires at least {minimum_images}",
                )
            if not any(media.is_primary for media in existing_local):
                record("missing_primary", subject, "no verified local primary image")

            for (first, first_hash), (second, second_hash) in combinations(hashes, 2):
                distance = (int(first_hash, 16) ^ int(second_hash, 16)).bit_count()
                if distance <= 4:
                    record(
                        "near_duplicate_perceptual_hash",
                        subject,
                        f"media#{first.pk} and media#{second.pk} have Hamming distance {distance}",
                    )

        for digest, media_subjects in sha_media.items():
            if len(media_subjects) > 1:
                record(
                    "duplicate_sha256",
                    digest[:12],
                    f"used by {len(media_subjects)} media: {', '.join(media_subjects[:4])}",
                )

        self._write_report(
            published_count=published_count,
            minimum_products=minimum_products,
            minimum_images=minimum_images,
            verified_image_total=verified_image_total,
            local_image_total=local_image_total,
            category_distribution=category_distribution,
            issues=issues,
            examples=examples,
        )

        total_issues = sum(issues.values())
        if options["strict"] and total_issues:
            raise CommandError(f"Catalog audit failed: {total_issues} issue(s).")

    @staticmethod
    def _is_hex(value, expected_length):
        if len(value) != expected_length:
            return False
        try:
            int(value, 16)
        except ValueError:
            return False
        return True

    @staticmethod
    def _file_exists(media):
        if not media.image_file or not media.image_file.name:
            return False
        try:
            return media.image_file.storage.exists(media.image_file.name)
        except (OSError, ValueError):
            return False

    @staticmethod
    def _meaningful(value):
        if isinstance(value, dict):
            return any(Command._meaningful(item) for item in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(Command._meaningful(item) for item in value)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    def _audit_localization(self, product, subject, record):
        for language in ("ka", "en", "ru"):
            if not (getattr(product, f"name_{language}", "") or "").strip():
                record("missing_localized_name", subject, f"name_{language} is empty")
            descriptions = (
                getattr(product, f"short_description_{language}", ""),
                getattr(product, f"full_description_{language}", ""),
            )
            if not any((value or "").strip() for value in descriptions):
                record(
                    "missing_localized_description",
                    subject,
                    f"short/full description for {language} is empty",
                )

    def _audit_specs(self, product, subject, record):
        json_specs = self._meaningful(product.specs)
        structured_specs = any(
            (specification.value or "").strip()
            for specification in product.audit_specification_values
        )
        if not json_specs and not structured_specs:
            record("missing_specs", subject, "no meaningful JSON or structured specification values")

    @staticmethod
    def _audit_dimensions(media, subject, record):
        required = (1200, 900) if media.is_primary else (1000, 720)
        try:
            with media.image_file.storage.open(media.image_file.name, "rb") as handle:
                with Image.open(handle) as image:
                    width, height = image.size
        except (OSError, ValueError, Image.UnidentifiedImageError) as exc:
            record("unreadable_image", subject, f"cannot read dimensions ({exc})")
            return

        long_edge, short_edge = max(width, height), min(width, height)
        if long_edge < required[0] or short_edge < required[1]:
            role = "primary" if media.is_primary else "secondary"
            record(
                "image_dimensions",
                subject,
                f"{role} is {width}x{height}; requires at least {required[0]}x{required[1]} in either orientation",
            )

    def _write_report(
        self,
        *,
        published_count,
        minimum_products,
        minimum_images,
        verified_image_total,
        local_image_total,
        category_distribution,
        issues,
        examples,
    ):
        total_issues = sum(issues.values())
        status = "PASS" if total_issues == 0 else "FAIL"
        self.stdout.write(f"Catalog audit: {status}")
        self.stdout.write(
            f"Published products: {published_count}/{minimum_products} minimum | "
            f"verified images: {verified_image_total} | local files: {local_image_total} | "
            f"minimum images/product: {minimum_images}"
        )
        self.stdout.write(f"Categories ({len(category_distribution)}):")
        if category_distribution:
            for slug, count in sorted(category_distribution.items()):
                self.stdout.write(f"  {slug}: {count}")
        else:
            self.stdout.write("  (none)")

        if not issues:
            self.stdout.write(self.style.SUCCESS("PASS: all catalog requirements satisfied."))
            return

        self.stdout.write(f"Issues: {total_issues} across {len(issues)} rule(s)")
        for rule, count in sorted(issues.items(), key=lambda item: (-item[1], item[0])):
            self.stdout.write(f"  {rule}: {count}")
            for example in examples[rule]:
                self.stdout.write(f"    - {example}")
            hidden = count - len(examples[rule])
            if hidden > 0:
                self.stdout.write(f"    - ... {hidden} more")
