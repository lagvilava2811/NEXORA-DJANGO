"""Create a portable NEXORA archive with optimized local product media.

The source project is never modified. Product image paths are preserved while
their archive copies are resized and recompressed as WebP/JPEG where possible.
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps


IMAGE_SUFFIXES = {".webp", ".jpg", ".jpeg", ".png"}
EXCLUDED_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "staticfiles"}
EXCLUDED_NAMES = {".env", "db.sqlite3"}
EXCLUDED_FILE_PATTERNS = {
    "*.log",
    ".codex-write-probe",
    "preview*",
    "catalog-sync*",
    "gallery-enrich*",
    "archive-export*",
    "browser-server*",
    "light-archive*",
    "overnight-*",
}


def is_excluded(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return (
        any(part in EXCLUDED_PARTS for part in relative.parts)
        or path.name in EXCLUDED_NAMES
        or any(fnmatch.fnmatch(path.name, pattern) for pattern in EXCLUDED_FILE_PATTERNS)
        or path.suffix.lower() == ".zip"
        or relative.parts[:2] == ("media", ".wikidata-staging")
    )


def optimized_image_bytes(path: Path, maximum: int, quality: int) -> bytes | None:
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            suffix = path.suffix.lower()
            if suffix == ".webp":
                if image.mode not in {"RGB", "RGBA"}:
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                image.save(output, "WEBP", quality=quality, method=6, alpha_quality=90)
            elif suffix in {".jpg", ".jpeg"}:
                image.convert("RGB").save(output, "JPEG", quality=quality, optimize=True, progressive=True)
            elif suffix == ".png":
                image.save(output, "PNG", optimize=True)
            else:
                return None
            return output.getvalue()
    except (OSError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maximum", type=int, default=1400)
    parser.add_argument("--quality", type=int, default=76)
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output.resolve()
    files = [path for path in root.rglob("*") if path.is_file() and not is_excluded(path, root)]
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    media_prefix = Path("media") / "product_uploads"
    optimized = 0
    original_bytes = 0
    archived_bytes = 0
    media_files = [
        path for path in files
        if path.relative_to(root).parts[:2] == media_prefix.parts
        and path.suffix.lower() in IMAGE_SUFFIXES
        and path.stat().st_size > 1024
    ]
    with ThreadPoolExecutor(max_workers=8) as pool:
        image_jobs = {
            path: pool.submit(optimized_image_bytes, path, args.maximum, args.quality)
            for path in media_files
        }
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in files:
                relative = path.relative_to(root)
                if path in image_jobs:
                    original_bytes += path.stat().st_size
                    payload = image_jobs[path].result()
                    if payload is not None:
                        archive.writestr(relative.as_posix(), payload, compress_type=zipfile.ZIP_STORED)
                        optimized += 1
                        archived_bytes += len(payload)
                        if optimized % 100 == 0:
                            print(f"optimized {optimized} product images", flush=True)
                        continue
                archive.write(path, relative.as_posix())

    print(f"archive={output}")
    print(f"optimized_images={optimized}")
    print(f"media_before_mb={original_bytes / 1024 / 1024:.1f}")
    print(f"media_after_mb={archived_bytes / 1024 / 1024:.1f}")
    print(f"archive_mb={output.stat().st_size / 1024 / 1024:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
