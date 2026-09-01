"""Install the compact, source-controlled catalogue used by the public demo.

The normal production catalogue lives in object storage.  The public Render demo
uses this smaller set so an empty managed database never produces an empty shop.
The command is deliberately idempotent: it only seeds a database with no products.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from store.models import Product


PRESENTATION_PRODUCT_TARGET = 200


class Command(BaseCommand):
    help = "Seed the compact NEXORA presentation catalogue when the database is empty."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Load the fixture even if products already exist (normally unnecessary).",
        )

    def handle(self, *args, **options):
        # These two compact data artefacts live at the repository root so they
        # can also be uploaded through GitHub's browser uploader when needed.
        fixture = Path(settings.BASE_DIR) / "render_presentation_catalog.json"
        assets_archive = Path(settings.BASE_DIR) / "render_presentation_catalog_media.zip"
        if not fixture.is_file() or not assets_archive.is_file():
            raise RuntimeError("Presentation catalogue fixture or local media is missing.")

        # Render's filesystem is recreated on every deploy.  Copy the committed
        # demo media before loading ProductMedia rows that reference it.  The
        # archive keeps the Git clone compact while retaining every gallery view.
        Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(assets_archive, settings.MEDIA_ROOT, format="zip")

        # Render recreates the container filesystem on every deploy while its
        # PostgreSQL database persists. Restore media every time. A previous
        # smaller demo seed (45 products) is upgraded in place on deployment;
        # once the complete presentation set exists, do not reload it.
        if Product.objects.count() >= PRESENTATION_PRODUCT_TARGET and not options["force"]:
            self.stdout.write("Presentation catalogue already complete; media restored.")
            return

        call_command("loaddata", str(fixture), verbosity=options["verbosity"])
        self.stdout.write(self.style.SUCCESS(
            f"Seeded/upgraded to {Product.objects.count()} NEXORA presentation products."
        ))
