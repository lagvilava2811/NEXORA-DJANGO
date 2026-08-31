"""Install the compact, source-controlled catalogue used by the public demo.

The normal production catalogue lives in object storage. The public Render demo
uses this smaller set so an empty managed database never produces an empty shop.
The command is idempotent: it only seeds a database with no products.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from store.models import Product


class Command(BaseCommand):
    help = "Seed the compact NEXORA presentation catalogue when the database is empty."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Load the fixture even if products already exist.",
        )

    def handle(self, *args, **options):
        if Product.objects.exists() and not options["force"]:
            self.stdout.write("Presentation catalogue already present; skipped.")
            return

        fixture = Path(settings.BASE_DIR) / "render_presentation_catalog.json"
        assets_archive = Path(settings.BASE_DIR) / "render_presentation_catalog_media.zip"
        if not fixture.is_file() or not assets_archive.is_file():
            raise RuntimeError("Presentation catalogue fixture or local media is missing.")

        Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(assets_archive, settings.MEDIA_ROOT, format="zip")
        call_command("loaddata", str(fixture), verbosity=options["verbosity"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Product.objects.count()} NEXORA presentation products."
            )
        )
